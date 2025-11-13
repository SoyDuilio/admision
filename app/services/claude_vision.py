import os
import base64
from typing import List, Optional

# Intentar importar Anthropic
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  Anthropic no instalado. Ejecuta: pip install anthropic")


class ClaudeVisionService:
    """
    Servicio para procesar imágenes con Anthropic Claude Vision API
    """
    
    def __init__(self):
        self.client = None
        self.available = False
        
        if not ANTHROPIC_AVAILABLE:
            print("❌ Anthropic SDK no está instalado")
            return
        
        # Obtener API key del entorno
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            print("⚠️  ANTHROPIC_API_KEY no configurado en .env")
            return
        
        try:
            self.client = Anthropic(api_key=api_key)
            self.available = True
            print("✅ Anthropic Claude Vision inicializado correctamente")
        except Exception as e:
            print(f"❌ Error inicializando Anthropic: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.available and self.client is not None
    
    async def extraer_respuestas(self, imagen_bytes: bytes) -> List[dict]:
        """
        Extrae respuestas de una hoja de respuestas usando Claude Vision
        
        Args:
            imagen_bytes: Bytes de la imagen a procesar
            
        Returns:
            List[dict]: Lista de respuestas detectadas
        """
        if not self.is_available():
            raise Exception(
                "Anthropic Claude Vision no está disponible. "
                "Verifica ANTHROPIC_API_KEY en tu archivo .env"
            )
        
        try:
            # Convertir bytes a base64
            base64_image = base64.b64encode(imagen_bytes).decode('utf-8')
            
            # Determinar el media type
            media_type = self._detectar_media_type(imagen_bytes)
            
            # Crear el prompt para Claude
            prompt = """
Analiza esta hoja de respuestas de examen de admisión.

La hoja contiene 100 preguntas numeradas del 1 al 100.
Cada pregunta tiene 5 alternativas: a, b, c, d, e.
El postulante marcó UNA alternativa por pregunta.

Extrae las 100 respuestas y devuelve SOLO un objeto JSON con este formato:

{
  "respuestas": [
    {"pregunta": 1, "respuesta": "a"},
    {"pregunta": 2, "respuesta": "b"},
    ...
    {"pregunta": 100, "respuesta": "e"}
  ]
}

IMPORTANTE: 
- Devuelve ÚNICAMENTE el JSON, sin explicaciones
- Todas las 100 preguntas deben estar
- Respuestas válidas: "a", "b", "c", "d", "e" o null si no hay marca
"""
            
            # Llamar a Claude Vision
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            # Extraer el contenido
            contenido = response.content[0].text
            print(f"📄 Respuesta de Claude recibida ({len(contenido)} caracteres)")
            
            # Parsear la respuesta
            respuestas = self._parsear_respuesta_claude(contenido)
            
            return respuestas
            
        except Exception as e:
            print(f"❌ Error en Anthropic Claude Vision: {e}")
            raise
    
    def _detectar_media_type(self, imagen_bytes: bytes) -> str:
        """Detecta el tipo MIME de la imagen"""
        # Verificar los primeros bytes (magic numbers)
        if imagen_bytes.startswith(b'\xff\xd8\xff'):
            return "image/jpeg"
        elif imagen_bytes.startswith(b'\x89PNG'):
            return "image/png"
        elif imagen_bytes.startswith(b'WEBP', 8):
            return "image/webp"
        else:
            # Default a JPEG
            return "image/jpeg"
    
    def _parsear_respuesta_claude(self, contenido: str) -> List[dict]:
        """
        Parsea la respuesta JSON de Claude
        
        Args:
            contenido: Respuesta de Claude (debe ser JSON)
            
        Returns:
            Lista de respuestas estandarizada
        """
        import json
        import re
        
        try:
            # Limpiar el contenido
            contenido_limpio = contenido.strip()
            
            # Remover bloques de código markdown si existen
            contenido_limpio = re.sub(r'```json\s*', '', contenido_limpio)
            contenido_limpio = re.sub(r'```\s*$', '', contenido_limpio)
            
            # Parsear JSON
            data = json.loads(contenido_limpio)
            
            # Convertir al formato estandarizado
            respuestas = []
            for item in data.get('respuestas', []):
                respuestas.append({
                    "numero_pregunta": item['pregunta'],
                    "respuesta_detectada": item['respuesta'],
                    "confianza": 95.0  # Claude no devuelve confianza, valor fijo alto
                })
            
            # Verificar que tengamos 100 respuestas
            if len(respuestas) != 100:
                print(f"⚠️  Se esperaban 100 respuestas, se obtuvieron {len(respuestas)}")
            
            return respuestas
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON de Claude: {e}")
            print(f"Contenido recibido: {contenido[:500]}...")
            raise Exception("Claude no devolvió un JSON válido")
        except Exception as e:
            print(f"❌ Error procesando respuesta de Claude: {e}")
            raise


# ===== SINGLETON =====
claude_vision_service = ClaudeVisionService()


# ===== FUNCIÓN DE TEST =====
def test_anthropic_vision():
    """Función para probar si Anthropic Vision está configurado"""
    print("\n" + "="*50)
    print("🧪 TEST: Anthropic Claude Vision Service")
    print("="*50)
    
    service = ClaudeVisionService()
    
    print(f"\n📊 Estado:")
    print(f"  - Módulo instalado: {ANTHROPIC_AVAILABLE}")
    print(f"  - Servicio disponible: {service.is_available()}")
    print(f"  - Cliente inicializado: {service.client is not None}")
    
    print(f"\n🔧 Variables de entorno:")
    api_key = os.getenv('ANTHROPIC_API_KEY', '')
    if api_key:
        print(f"  - ANTHROPIC_API_KEY: {api_key[:10]}...{api_key[-4:]}")
    else:
        print(f"  - ANTHROPIC_API_KEY: No configurado")
    
    print("\n" + "="*50 + "\n")
    
    return service.is_available()


if __name__ == "__main__":
    test_anthropic_vision()