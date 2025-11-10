"""
Orquestador de Vision APIs
Coordina las 3 APIs de Vision (Google, OpenAI, Claude) con sistema de fallback
"""

import logging
import time
from typing import List, Dict, Tuple, Optional

from app.config import settings
from app.schemas.respuesta import RespuestaDetectada, VisionAPIResponse
from app.services.google_vision import google_vision_service
from app.services.openai_vision import openai_vision_service
from app.services.claude_vision import claude_vision_service

logger = logging.getLogger(__name__)


class VisionOrchestrator:
    """
    Orquestador de Vision APIs
    
    Maneja la lógica de:
    - Selección de API primaria
    - Fallback automático si una API falla
    - Métricas de rendimiento
    - Logging de uso
    """
    
    def __init__(self):
        """Inicializa el orquestador"""
        self.services = {
            "google": google_vision_service,
            "openai": openai_vision_service,
            "claude": claude_vision_service
        }
        
        # Orden de prioridad para fallback
        self.priority_order = self._determine_priority_order()
        
        logger.info(f"🎯 Orden de prioridad Vision APIs: {self.priority_order}")
    
    def _determine_priority_order(self) -> List[str]:
        """
        Determina el orden de prioridad de las APIs basado en disponibilidad
        
        Returns:
            Lista de nombres de APIs en orden de prioridad
        """
        # Orden configurado por el usuario
        primary = settings.vision_primary
        
        # Verificar disponibilidad
        available = []
        for api_name, service in self.services.items():
            if service.is_available():
                available.append(api_name)
        
        # Construir orden de prioridad
        priority = []
        
        # 1. Primero la API primaria si está disponible
        if primary in available:
            priority.append(primary)
            available.remove(primary)
        
        # 2. Luego el resto en orden: google, claude, openai
        preferred_order = ["google", "claude", "openai"]
        for api in preferred_order:
            if api in available and api not in priority:
                priority.append(api)
        
        if not priority:
            logger.error("❌ CRÍTICO: No hay ninguna Vision API disponible")
            raise Exception("No hay Vision APIs disponibles")
        
        return priority
    
    async def process_image(
        self,
        image_path: str,
        tipo: str = "estudiante",
        force_api: Optional[str] = None
    ) -> VisionAPIResponse:
        """
        Procesa una imagen con el sistema de fallback
        
        Args:
            image_path: Ruta a la imagen
            tipo: "estudiante" o "clave"
            force_api: Forzar uso de una API específica (opcional)
        
        Returns:
            VisionAPIResponse con los resultados
        """
        # Si se fuerza una API específica
        if force_api:
            if force_api not in self.services:
                raise ValueError(f"API '{force_api}' no existe")
            
            if not self.services[force_api].is_available():
                raise Exception(f"API '{force_api}' no está disponible")
            
            return await self._process_with_api(
                image_path, 
                tipo, 
                force_api
            )
        
        # Probar con fallback
        last_error = None
        
        for api_name in self.priority_order:
            try:
                logger.info(f"🔄 Intentando con {api_name.upper()}...")
                
                result = await self._process_with_api(
                    image_path,
                    tipo,
                    api_name
                )
                
                if result.success:
                    logger.info(f"✅ Éxito con {api_name.upper()}")
                    return result
                else:
                    logger.warning(f"⚠️ {api_name.upper()} retornó sin éxito: {result.error_message}")
                    last_error = result.error_message
                    
            except Exception as e:
                logger.error(f"❌ Error con {api_name.upper()}: {e}")
                last_error = str(e)
                continue
        
        # Si llegamos aquí, todas las APIs fallaron
        logger.error("❌ TODAS las Vision APIs fallaron")
        
        return VisionAPIResponse(
            success=False,
            api_usada="ninguna",
            tiempo_procesamiento=0.0,
            respuestas=[],
            total_detectadas=0,
            confianza_promedio=0.0,
            error_message=f"Todas las APIs fallaron. Último error: {last_error}"
        )
    
    async def _process_with_api(
        self,
        image_path: str,
        tipo: str,
        api_name: str
    ) -> VisionAPIResponse:
        """
        Procesa imagen con una API específica
        
        Args:
            image_path: Ruta a la imagen
            tipo: "estudiante" o "clave"
            api_name: Nombre de la API a usar
        
        Returns:
            VisionAPIResponse
        """
        service = self.services[api_name]
        
        start_time = time.time()
        
        try:
            # Llamar al servicio
            respuestas, metadata = await service.extract_answers(
                image_path=image_path,
                tipo=tipo
            )
            
            # Calcular tiempo
            tiempo_procesamiento = time.time() - start_time
            
            # Validar resultados
            if len(respuestas) != 100:
                logger.warning(f"⚠️ {api_name} detectó {len(respuestas)}/100 respuestas")
            
            # Calcular confianza promedio
            confianza_promedio = sum(r.confianza for r in respuestas) / len(respuestas) if respuestas else 0.0
            
            return VisionAPIResponse(
                success=True,
                api_usada=api_name,
                tiempo_procesamiento=tiempo_procesamiento,
                respuestas=respuestas,
                total_detectadas=len(respuestas),
                confianza_promedio=confianza_promedio,
                raw_response=metadata
            )
            
        except Exception as e:
            tiempo_procesamiento = time.time() - start_time
            
            logger.error(f"❌ Error en {api_name}: {e}")
            
            return VisionAPIResponse(
                success=False,
                api_usada=api_name,
                tiempo_procesamiento=tiempo_procesamiento,
                respuestas=[],
                total_detectadas=0,
                confianza_promedio=0.0,
                error_message=str(e)
            )
    
    async def process_image_base64(
        self,
        image_base64: str,
        tipo: str = "estudiante",
        media_type: str = "image/jpeg",
        force_api: Optional[str] = None
    ) -> VisionAPIResponse:
        """
        Procesa una imagen en base64 con el sistema de fallback
        
        Args:
            image_base64: Imagen codificada en base64
            tipo: "estudiante" o "clave"
            media_type: Tipo MIME de la imagen
            force_api: Forzar uso de una API específica
        
        Returns:
            VisionAPIResponse
        """
        # Si se fuerza una API
        if force_api:
            if force_api not in self.services:
                raise ValueError(f"API '{force_api}' no existe")
            
            if not self.services[force_api].is_available():
                raise Exception(f"API '{force_api}' no está disponible")
            
            return await self._process_base64_with_api(
                image_base64,
                tipo,
                media_type,
                force_api
            )
        
        # Probar con fallback
        last_error = None
        
        for api_name in self.priority_order:
            try:
                logger.info(f"🔄 Intentando con {api_name.upper()} (base64)...")
                
                result = await self._process_base64_with_api(
                    image_base64,
                    tipo,
                    media_type,
                    api_name
                )
                
                if result.success:
                    logger.info(f"✅ Éxito con {api_name.upper()}")
                    return result
                else:
                    logger.warning(f"⚠️ {api_name.upper()} falló: {result.error_message}")
                    last_error = result.error_message
                    
            except Exception as e:
                logger.error(f"❌ Error con {api_name.upper()}: {e}")
                last_error = str(e)
                continue
        
        # Todas fallaron
        return VisionAPIResponse(
            success=False,
            api_usada="ninguna",
            tiempo_procesamiento=0.0,
            respuestas=[],
            total_detectadas=0,
            confianza_promedio=0.0,
            error_message=f"Todas las APIs fallaron. Último error: {last_error}"
        )
    
    async def _process_base64_with_api(
        self,
        image_base64: str,
        tipo: str,
        media_type: str,
        api_name: str
    ) -> VisionAPIResponse:
        """Procesa imagen base64 con una API específica"""
        service = self.services[api_name]
        
        start_time = time.time()
        
        try:
            # Llamar al servicio
            respuestas, metadata = await service.extract_answers_from_base64(
                image_base64=image_base64,
                tipo=tipo
            )
            
            tiempo_procesamiento = time.time() - start_time
            
            # Validar
            if len(respuestas) != 100:
                logger.warning(f"⚠️ {api_name} detectó {len(respuestas)}/100 respuestas")
            
            confianza_promedio = sum(r.confianza for r in respuestas) / len(respuestas) if respuestas else 0.0
            
            return VisionAPIResponse(
                success=True,
                api_usada=api_name,
                tiempo_procesamiento=tiempo_procesamiento,
                respuestas=respuestas,
                total_detectadas=len(respuestas),
                confianza_promedio=confianza_promedio,
                raw_response=metadata
            )
            
        except Exception as e:
            tiempo_procesamiento = time.time() - start_time
            
            return VisionAPIResponse(
                success=False,
                api_usada=api_name,
                tiempo_procesamiento=tiempo_procesamiento,
                respuestas=[],
                total_detectadas=0,
                confianza_promedio=0.0,
                error_message=str(e)
            )
    
    def get_available_apis(self) -> List[str]:
        """Retorna lista de APIs disponibles"""
        return [
            name for name, service in self.services.items()
            if service.is_available()
        ]
    
    def get_api_status(self) -> Dict[str, bool]:
        """Retorna el estado de todas las APIs"""
        return {
            name: service.is_available()
            for name, service in self.services.items()
        }


# Instancia global del orquestador
vision_orchestrator = VisionOrchestrator()