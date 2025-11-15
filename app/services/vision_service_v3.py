"""
Vision Service V3 - Procesamiento Dividido en 2 Partes
app/services/vision_service_v3.py

ESTRATEGIA:
- Request 1 (GPT-4O): Metadatos + Respuestas 1-50
- Request 2 (GPT-4O-MINI): Respuestas 51-100
- Merge de resultados en paralelo

VENTAJAS:
- Más rápido (requests paralelos)
- Sin timeout (cada request es más corto)
- Mayor precisión (menos datos por request)
"""

import os
import base64
import json
import time
import asyncio
from typing import Dict, List, Optional, Tuple
import anthropic
from openai import OpenAI
import google.generativeai as genai

from app.services.json_parser_robust import parsear_respuesta_vision_api
from app.services.prompt_vision_dividido import (
    PROMPT_PARTE_1_METADATOS_Y_PRIMERA_MITAD,
    PROMPT_PARTE_2_SEGUNDA_MITAD,
    SYSTEM_MESSAGE_OPENAI,
    SUFFIX_CLAUDE,
    SUFFIX_GEMINI
)

# ============================================================================
# CONFIGURACIÓN DE APIs
# ============================================================================

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


# ============================================================================
# EXTRACCIÓN PARTE 1: METADATOS + PRIMERA MITAD
# ============================================================================

async def extraer_parte1_con_gpt4o(imagen_path: str) -> Dict:
    """
    Extrae metadatos + respuestas 1-50 con GPT-4O.
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MESSAGE_OPENAI
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT_PARTE_1_METADATOS_Y_PRIMERA_MITAD},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3000,
            temperature=0
        )
        
        texto_raw = response.choices[0].message.content.strip()
        
        print(f"📄 [PARTE 1 - GPT-4O] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        # Parsear
        datos = parsear_respuesta_vision_api(texto_raw)
        
        # Validar estructura
        if "respuestas" not in datos or len(datos["respuestas"]) != 50:
            return {
                "success": False,
                "error": f"Se esperaban 50 respuestas, se recibieron {len(datos.get('respuestas', []))}"
            }
        
        return {
            "success": True,
            "api": "gpt-4o",
            "parte": 1,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte1_con_gpt4o: {str(e)}")
        return {
            "success": False,
            "api": "gpt-4o",
            "parte": 1,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN PARTE 2: SEGUNDA MITAD
# ============================================================================

async def extraer_parte2_con_gpt4o_mini(imagen_path: str) -> Dict:
    """
    Extrae respuestas 51-100 con GPT-4O-MINI.
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MESSAGE_OPENAI
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT_PARTE_2_SEGUNDA_MITAD},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2500,
            temperature=0
        )
        
        texto_raw = response.choices[0].message.content.strip()
        
        print(f"📄 [PARTE 2 - GPT-4O-MINI] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        # Parsear
        datos = parsear_respuesta_vision_api(texto_raw)
        
        # Validar estructura
        if "respuestas" not in datos or len(datos["respuestas"]) != 50:
            return {
                "success": False,
                "error": f"Se esperaban 50 respuestas, se recibieron {len(datos.get('respuestas', []))}"
            }
        
        return {
            "success": True,
            "api": "gpt-4o-mini",
            "parte": 2,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte2_con_gpt4o_mini: {str(e)}")
        return {
            "success": False,
            "api": "gpt-4o-mini",
            "parte": 2,
            "error": str(e)
        }


# ============================================================================
# MERGE DE RESULTADOS
# ============================================================================

def merge_resultados_divididos(resultado1: Dict, resultado2: Dict) -> Dict:
    """
    Combina los resultados de las 2 partes.
    
    Args:
        resultado1: Parte 1 (metadatos + respuestas 1-50)
        resultado2: Parte 2 (respuestas 51-100)
        
    Returns:
        Dict con todos los datos combinados
    """
    
    if not resultado1["success"]:
        raise ValueError(f"Parte 1 falló: {resultado1.get('error')}")
    
    if not resultado2["success"]:
        raise ValueError(f"Parte 2 falló: {resultado2.get('error')}")
    
    datos1 = resultado1["datos"]
    datos2 = resultado2["datos"]
    
    # Combinar respuestas
    respuestas_completas = datos1["respuestas"] + datos2["respuestas"]
    
    # Validar total
    if len(respuestas_completas) != 100:
        raise ValueError(f"Total de respuestas inválido: {len(respuestas_completas)} (esperadas: 100)")
    
    # Resultado final
    return {
        "dni_postulante": datos1.get("dni_postulante", ""),
        "codigo_aula": datos1.get("codigo_aula", ""),
        "dni_profesor": datos1.get("dni_profesor", ""),
        "codigo_hoja": datos1.get("codigo_hoja", ""),
        "proceso_admision": datos1.get("proceso_admision", ""),
        "respuestas": respuestas_completas
    }


# ============================================================================
# FUNCIÓN PRINCIPAL - PROCESAMIENTO PARALELO
# ============================================================================

async def procesar_hoja_dividida(imagen_path: str) -> Dict:
    """
    Procesa una hoja dividiéndola en 2 requests paralelos.
    
    FLUJO:
    1. Request 1 (GPT-4O): Metadatos + Resp 1-50  → ~8 seg
    2. Request 2 (GPT-4O-MINI): Resp 51-100       → ~6 seg
    3. Merge de resultados
    
    Total: ~8-10 segundos (en paralelo)
    
    Args:
        imagen_path: Ruta de la imagen procesada con OpenCV
        
    Returns:
        Dict con todos los datos extraídos
    """
    
    inicio = time.time()
    
    print("\n" + "="*60)
    print("🚀 PROCESAMIENTO DIVIDIDO EN 2 PARTES (PARALELO)")
    print("="*60)
    print(f"📸 Imagen: {os.path.basename(imagen_path)}")
    
    try:
        # Ejecutar ambos requests EN PARALELO
        print("\n🔄 Iniciando requests paralelos...")
        print("   📍 Parte 1: GPT-4O (Metadatos + Resp 1-50)")
        print("   📍 Parte 2: GPT-4O-MINI (Resp 51-100)")
        
        resultado1, resultado2 = await asyncio.gather(
            extraer_parte1_con_gpt4o(imagen_path),
            extraer_parte2_con_gpt4o_mini(imagen_path)
        )
        
        print(f"\n✅ Parte 1: {'OK' if resultado1['success'] else 'FALLÓ'}")
        print(f"✅ Parte 2: {'OK' if resultado2['success'] else 'FALLÓ'}")
        
        # Merge
        print("\n🔗 Combinando resultados...")
        datos_completos = merge_resultados_divididos(resultado1, resultado2)
        
        tiempo_total = time.time() - inicio
        
        print("\n" + "="*60)
        print(f"✅ PROCESAMIENTO EXITOSO")
        print(f"⏱️  Tiempo total: {tiempo_total:.2f}s")
        print(f"📊 Metadatos extraídos:")
        print(f"   - DNI Postulante: {datos_completos['dni_postulante']}")
        print(f"   - Código Aula: {datos_completos['codigo_aula']}")
        print(f"   - Código Hoja: {datos_completos['codigo_hoja']}")
        print(f"📝 Respuestas: {len(datos_completos['respuestas'])}/100")
        print("="*60 + "\n")
        
        return {
            "success": True,
            "datos": datos_completos,
            "tiempo_procesamiento": tiempo_total,
            "metodo": "dividido_paralelo",
            "apis_usadas": ["gpt-4o", "gpt-4o-mini"]
        }
        
    except Exception as e:
        tiempo_total = time.time() - inicio
        print(f"\n❌ ERROR: {str(e)}")
        print(f"⏱️  Tiempo hasta error: {tiempo_total:.2f}s\n")
        
        return {
            "success": False,
            "error": str(e),
            "tiempo_procesamiento": tiempo_total,
            "metodo": "dividido_paralelo"
        }


# ============================================================================
# WRAPPER PARA COMPATIBILIDAD
# ============================================================================

async def procesar_hoja_completa_v3(imagen_path: str) -> Dict:
    """
    Alias para compatibilidad con el código existente.
    Usa el nuevo método dividido.
    """
    return await procesar_hoja_dividida(imagen_path)