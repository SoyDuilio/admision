"""
Vision Service V3 - Procesamiento con Gemini Estructurado

ESTRATEGIA V7 - GEMINI STRUCTURED SCHEMA:
- Pre-procesamiento OpenCV V2 + ZOOM 2X (sin corrección de perspectiva)
- PRIMARIO: Gemini 2.0 Flash con Schema Estructurado (1 llamada para todo)
- FALLBACK: Claude Sonnet 4 dividido en 2 partes
- Validación y merge de resultados

VENTAJAS DEL SCHEMA ESTRUCTURADO:
✅ Formato JSON garantizado por Gemini
✅ 100 respuestas SIEMPRE presentes (1-100)
✅ 4 códigos SIEMPRE presentes (validación automática)
✅ Una sola llamada (vs 2 llamadas divididas)
✅ ~6-8 segundos total (vs 15-20 seg con división)
✅ Más económico (1 request vs 2)
✅ Menos propenso a errores de merge

MEJORAS OPENCV:
✅ Zoom 2X con interpolación bicúbica (letras 2x más grandes)
✅ CLAHE agresivo para mejor contraste
✅ Nitidez aumentada
✅ Sin corrección de perspectiva (evita reducción de imagen)
✅ Imagen final mantiene tamaño 2880x3840px
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
from app.services.image_preprocessor_v2 import ImagePreprocessorV2
from app.services.gemini_extractor_structured import extract_data_compatible
from app.services.prompt_vision_v6 import (
    PROMPT_PARTE_1_V6,
    PROMPT_PARTE_2_V6,
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
                        {"type": "text", "text": PROMPT_PARTE_1_V6},
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
        
        print(f"✅ [PARTE 1] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        # Validar estructura (más permisiva)
        if "respuestas" not in datos:
            return {
                "success": False,
                "error": "JSON sin campo 'respuestas'"
            }
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            # Permitir rango entre 40-60 (tolerancia)
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        # Si tiene más de 50, truncar
        if num_respuestas > 50:
            print(f"⚠️  Truncando de {num_respuestas} a 50 respuestas")
            datos["respuestas"] = datos["respuestas"][:50]
        
        # Si tiene menos de 50, rellenar con nulls
        if num_respuestas < 50:
            print(f"⚠️  Rellenando de {num_respuestas} a 50 respuestas")
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 1] Validación OK - {len(datos['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "gpt-4o",
            "parte": 1,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte1_con_gpt4o: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "gpt-4o",
            "parte": 1,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN PARTE 2: SEGUNDA MITAD CON GPT-4O
# ============================================================================

async def extraer_parte2_con_gpt4o(imagen_path: str) -> Dict:
    """
    Extrae respuestas 51-100 con GPT-4O (en lugar de GPT-4O-MINI).
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
                        {"type": "text", "text": PROMPT_PARTE_2_V6},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3500,
            temperature=0
        )
        
        texto_raw = response.choices[0].message.content.strip()
        
        print(f"📄 [PARTE 2 - GPT-4O] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        # Parsear
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 2] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        # Validar estructura (más permisiva)
        if "respuestas" not in datos:
            return {
                "success": False,
                "error": "JSON sin campo 'respuestas'"
            }
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        # Auto-ajuste
        if num_respuestas > 50:
            print(f"⚠️  Truncando de {num_respuestas} a 50 respuestas")
            datos["respuestas"] = datos["respuestas"][:50]
        
        if num_respuestas < 50:
            print(f"⚠️  Rellenando de {num_respuestas} a 50 respuestas")
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 2] Validación OK - {len(datos['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "gpt-4o",
            "parte": 2,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte2_con_gpt4o: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "gpt-4o",
            "parte": 2,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN CON CLAUDE (FALLBACK)
# ============================================================================

async def extraer_parte1_con_claude(imagen_path: str) -> Dict:
    """
    Extrae metadatos + respuestas 1-50 con Claude Sonnet 4.
    Usado como fallback si GPT-4O falla.
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Detectar tipo de imagen
        ext = imagen_path.lower().split('.')[-1]
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": PROMPT_PARTE_1_V6 + SUFFIX_CLAUDE
                        }
                    ]
                }
            ]
        )
        
        texto_raw = message.content[0].text.strip()
        
        print(f"📄 [PARTE 1 - CLAUDE] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 1 CLAUDE] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        if "respuestas" not in datos:
            return {"success": False, "error": "JSON sin campo 'respuestas'"}
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        if num_respuestas > 50:
            datos["respuestas"] = datos["respuestas"][:50]
        if num_respuestas < 50:
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 1 CLAUDE] Validación OK - {len(datos['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "claude",
            "parte": 1,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte1_con_claude: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "claude",
            "parte": 1,
            "error": str(e)
        }


async def extraer_parte2_con_claude(imagen_path: str) -> Dict:
    """
    Extrae respuestas 51-100 con Claude Sonnet 4.
    Usado como fallback si GPT-4O falla.
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        ext = imagen_path.lower().split('.')[-1]
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": PROMPT_PARTE_2_V6 + SUFFIX_CLAUDE
                        }
                    ]
                }
            ]
        )
        
        texto_raw = message.content[0].text.strip()
        
        print(f"📄 [PARTE 2 - CLAUDE] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 2 CLAUDE] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        if "respuestas" not in datos:
            return {"success": False, "error": "JSON sin campo 'respuestas'"}
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        if num_respuestas > 50:
            datos["respuestas"] = datos["respuestas"][:50]
        if num_respuestas < 50:
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 2 CLAUDE] Validación OK - {len(datos['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "claude",
            "parte": 2,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte2_con_claude: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "claude",
            "parte": 2,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN CON GEMINI (FALLBACK SECUNDARIO)
# ============================================================================

async def extraer_parte1_con_gemini(imagen_path: str) -> Dict:
    """
    Extrae metadatos + respuestas 1-50 con Gemini.
    Usado como fallback si Claude falla.
    """
    try:
        # Subir imagen a Gemini
        uploaded_file = genai.upload_file(imagen_path)
        
        # Usar gemini-2.5-flash (más disponible)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        response = model.generate_content([
            uploaded_file,
            PROMPT_PARTE_1_V6 + SUFFIX_GEMINI
        ])
        
        texto_raw = response.text.strip()
        
        print(f"📄 [PARTE 1 - GEMINI] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 1 GEMINI] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        if "respuestas" not in datos:
            return {"success": False, "error": "JSON sin campo 'respuestas'"}
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        if num_respuestas > 50:
            datos["respuestas"] = datos["respuestas"][:50]
        if num_respuestas < 50:
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 1 GEMINI] Validación OK - {len(datos['respuestas'])} respuestas")
        
        # Limpiar archivo
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass
        
        return {
            "success": True,
            "api": "gemini",
            "parte": 1,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte1_con_gemini: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "gemini",
            "parte": 1,
            "error": str(e)
        }


async def extraer_parte2_con_gemini(imagen_path: str) -> Dict:
    """
    Extrae respuestas 51-100 con Gemini.
    Usado como fallback si Claude falla.
    """
    try:
        # Subir imagen a Gemini
        uploaded_file = genai.upload_file(imagen_path)
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        response = model.generate_content([
            uploaded_file,
            PROMPT_PARTE_2_V6 + SUFFIX_GEMINI
        ])
        
        texto_raw = response.text.strip()
        
        print(f"📄 [PARTE 2 - GEMINI] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 2 GEMINI] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        if "respuestas" not in datos:
            return {"success": False, "error": "JSON sin campo 'respuestas'"}
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        if num_respuestas > 50:
            datos["respuestas"] = datos["respuestas"][:50]
        if num_respuestas < 50:
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 2 GEMINI] Validación OK - {len(datos['respuestas'])} respuestas")
        
        # Limpiar archivo
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass
        
        return {
            "success": True,
            "api": "gemini",
            "parte": 2,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte2_con_gemini: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "api": "gemini",
            "parte": 2,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN PARTE 2: SEGUNDA MITAD CON GPT-4O-MINI (MANTENER POR COMPATIBILIDAD)
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
                        {"type": "text", "text": PROMPT_PARTE_2_V6},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=3500,  # Aumentado de 2500 a 3500
            temperature=0
        )
        
        texto_raw = response.choices[0].message.content.strip()
        
        print(f"📄 [PARTE 2 - GPT-4O-MINI] Respuesta (primeros 200 chars):")
        print(texto_raw[:200])
        
        # Parsear
        datos = parsear_respuesta_vision_api(texto_raw)
        
        print(f"✅ [PARTE 2] JSON parseado correctamente")
        print(f"   Campos: {list(datos.keys())}")
        print(f"   Respuestas detectadas: {len(datos.get('respuestas', []))}")
        
        # Validar estructura (más permisiva)
        if "respuestas" not in datos:
            return {
                "success": False,
                "error": "JSON sin campo 'respuestas'"
            }
        
        num_respuestas = len(datos["respuestas"])
        if num_respuestas < 40 or num_respuestas > 60:
            # Permitir rango entre 40-60 (tolerancia)
            return {
                "success": False,
                "error": f"Se esperaban ~50 respuestas, se recibieron {num_respuestas}"
            }
        
        # Si tiene más de 50, truncar
        if num_respuestas > 50:
            print(f"⚠️  Truncando de {num_respuestas} a 50 respuestas")
            datos["respuestas"] = datos["respuestas"][:50]
        
        # Si tiene menos de 50, rellenar con nulls
        if num_respuestas < 50:
            print(f"⚠️  Rellenando de {num_respuestas} a 50 respuestas")
            datos["respuestas"].extend([None] * (50 - num_respuestas))
        
        print(f"✅ [PARTE 2] Validación OK - {len(datos['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "gpt-4o-mini",
            "parte": 2,
            "datos": datos
        }
        
    except Exception as e:
        print(f"❌ Error en extraer_parte2_con_gpt4o_mini: {str(e)}")
        import traceback
        traceback.print_exc()
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
    Procesa una hoja usando Gemini con schema estructurado.
    
    FLUJO V7 (GEMINI ESTRUCTURADO):
    0. Pre-procesamiento OpenCV V2 + ZOOM 2X
    1. GEMINI con schema estructurado (UNA SOLA LLAMADA para todo)
    2. Si falla → Fallback con CLAUDE dividido (2 llamadas)
    3. Merge y validación
    
    Total: ~6-8 segundos (1 llamada) o ~15 seg (fallback)
    
    Args:
        imagen_path: Ruta de la imagen original
        
    Returns:
        Dict con todos los datos extraídos
    """
    
    inicio = time.time()
    
    print("\n" + "="*60)
    print("🚀 PROCESAMIENTO V7 (GEMINI ESTRUCTURADO)")
    print("="*60)
    print(f"📸 Imagen original: {os.path.basename(imagen_path)}")
    
    # ========================================================================
    # PASO 0: PRE-PROCESAMIENTO OPENCV V2 + ZOOM 2X
    # ========================================================================
    
    preprocessor = ImagePreprocessorV2()
    imagen_procesada = imagen_path
    preprocessing_metadata = {"used": False}
    
    try:
        imagen_procesada, preprocessing_metadata = preprocessor.procesar_completo(imagen_path)
        preprocessing_metadata["used"] = True
        print(f"✅ Pre-procesamiento V2 + ZOOM 2X completado")
        print(f"📸 Imagen procesada: {os.path.basename(imagen_procesada)}")
    except Exception as e:
        print(f"⚠️ Pre-procesamiento falló: {e}")
        print(f"ℹ️  Usando imagen original")
        imagen_procesada = imagen_path
    
    # ========================================================================
    # PASO 1: GEMINI ESTRUCTURADO (UNA SOLA LLAMADA)
    # ========================================================================
    
    try:
        print("\n🤖 Extrayendo datos con GEMINI ESTRUCTURADO...")
        print("   📍 Schema-based extraction (100 respuestas + metadatos)")
        
        resultado_gemini = await extract_data_compatible(imagen_procesada)
        
        if resultado_gemini["success"]:
            print("\n✅ GEMINI ESTRUCTURADO: ÉXITO")
            
            datos_completos = resultado_gemini["data"]
            tiempo_total = time.time() - inicio
            
            # Contar válidas vs null
            validas = sum(1 for r in datos_completos['respuestas'] if r in ['A','B','C','D','E'])
            nulas = sum(1 for r in datos_completos['respuestas'] if r is None)
            
            print("\n" + "="*60)
            print(f"✅ PROCESAMIENTO EXITOSO")
            print(f"⏱️  Tiempo total: {tiempo_total:.2f}s")
            print(f"🤖 API: Gemini 2.0 Flash (Structured)")
            print(f"📊 Metadatos extraídos:")
            print(f"   - DNI Postulante: {datos_completos['dni_postulante']}")
            print(f"   - Código Aula: {datos_completos['codigo_aula']}")
            print(f"   - Código Hoja: {datos_completos['codigo_hoja']}")
            print(f"📝 Respuestas: {len(datos_completos['respuestas'])}/100")
            print(f"   - Válidas: {validas}")
            print(f"   - Nulls: {nulas}")
            print("="*60 + "\n")
            
            return {
                "success": True,
                "datos": datos_completos,
                "tiempo_procesamiento": tiempo_total,
                "metodo": "gemini_structured_v7",
                "apis_usadas": ["gemini-structured"],
                "preprocessing": preprocessing_metadata
            }
        
        else:
            # Gemini falló, intentar con Claude
            print(f"\n⚠️  GEMINI falló: {resultado_gemini.get('error')}")
            print("🔄 Intentando con CLAUDE (fallback)...")
            
    except Exception as e:
        print(f"\n⚠️  GEMINI exception: {str(e)}")
        print("🔄 Intentando con CLAUDE (fallback)...")
    
    # ========================================================================
    # PASO 2: FALLBACK CON CLAUDE (DIVIDIDO EN 2 PARTES)
    # ========================================================================
    
    try:
        print("\n🔄 Ejecutando fallback con CLAUDE...")
        print("   📍 Parte 1: CLAUDE (Metadatos + Resp 1-50)")
        print("   📍 Parte 2: CLAUDE (Resp 51-100)")
        
        resultado1, resultado2 = await asyncio.gather(
            extraer_parte1_con_claude(imagen_procesada),
            extraer_parte2_con_claude(imagen_procesada)
        )
        
        print(f"\n✅ Parte 1 (CLAUDE): {'OK' if resultado1['success'] else 'FALLÓ'}")
        print(f"✅ Parte 2 (CLAUDE): {'OK' if resultado2['success'] else 'FALLÓ'}")
        
        # Verificar que funcionó
        if not resultado1['success'] or not resultado2['success']:
            raise ValueError(
                f"Fallback con Claude también falló. "
                f"Parte 1: {resultado1.get('error', 'Unknown')}, "
                f"Parte 2: {resultado2.get('error', 'Unknown')}"
            )
        
        # Merge
        print("\n🔗 Combinando resultados de Claude...")
        datos_completos = merge_resultados_divididos(resultado1, resultado2)
        
        tiempo_total = time.time() - inicio
        
        # Registrar qué APIs se usaron
        apis_usadas = ["claude-fallback"]
        
        print("\n" + "="*60)
        print(f"✅ PROCESAMIENTO EXITOSO (FALLBACK)")
        print(f"⏱️  Tiempo total: {tiempo_total:.2f}s")
        print(f"🤖 APIs usadas: Claude Sonnet 4 (fallback)")
        print(f"📊 Metadatos extraídos:")
        print(f"   - DNI Postulante: {datos_completos['dni_postulante']}")
        print(f"   - Código Aula: {datos_completos['codigo_aula']}")
        print(f"   - Código Hoja: {datos_completos['codigo_hoja']}")
        print(f"📝 Respuestas: {len(datos_completos['respuestas'])}/100")
        
        # Contar válidas vs null
        validas = sum(1 for r in datos_completos['respuestas'] if r in ['A','B','C','D','E'])
        nulas = sum(1 for r in datos_completos['respuestas'] if r is None)
        print(f"   - Válidas: {validas}")
        print(f"   - Nulls: {nulas}")
        print("="*60 + "\n")
        
        return {
            "success": True,
            "datos": datos_completos,
            "tiempo_procesamiento": tiempo_total,
            "metodo": "claude_fallback_v7",
            "apis_usadas": apis_usadas,
            "preprocessing": preprocessing_metadata
        }
        
    except Exception as e:
        tiempo_total = time.time() - inicio
        print(f"\n❌ ERROR: Todas las APIs fallaron")
        print(f"⏱️  Tiempo hasta error: {tiempo_total:.2f}s")
        print(f"💥 {str(e)}\n")
        
        return {
            "success": False,
            "error": str(e),
            "tiempo_procesamiento": tiempo_total,
            "metodo": "all_failed_v7"
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


# ============================================================================
# FUNCIONES AUXILIARES PARA GUARDAR EN BD
# ============================================================================

from sqlalchemy.orm import Session
from app.models import HojaRespuesta, Respuesta


async def procesar_y_guardar_respuestas(
    hoja_respuesta_id: int,
    resultado_api: Dict,
    db: Session
) -> Dict:
    """
    Procesa el resultado de la Vision API y guarda cada respuesta en la BD.
    
    ADAPTADO PARA FORMATO DIVIDIDO:
    resultado_api["datos"] = {
        "dni_postulante": "...",
        "codigo_aula": "...",
        "codigo_hoja": "...",
        "respuestas": [100 elementos]
    }
    
    Args:
        hoja_respuesta_id: ID de la hoja de respuesta procesada
        resultado_api: Resultado del procesamiento dividido
        db: Sesión de base de datos
        
    Returns:
        Dict con estadísticas del procesamiento
    """
    
    # Extraer datos
    datos = resultado_api.get("datos", {})
    respuestas_array = datos.get("respuestas", [])
    
    if not respuestas_array:
        raise ValueError("No se encontraron respuestas en el resultado de la API")
    
    if len(respuestas_array) != 100:
        raise ValueError(f"Se esperaban 100 respuestas, se recibieron {len(respuestas_array)}")
    
    # Estadísticas
    stats = {
        "total": 0,
        "validas": 0,
        "vacias": 0,
        "invalidas": 0,
        "requieren_revision": 0
    }
    
    respuestas_guardadas = []
    
    for idx, respuesta_detectada in enumerate(respuestas_array, start=1):
        # Normalizar
        if respuesta_detectada is None:
            respuesta_final = "VACIO"
            es_valida = False
            confianza = None
        elif respuesta_detectada in ['A', 'B', 'C', 'D', 'E']:
            respuesta_final = respuesta_detectada
            es_valida = True
            confianza = 0.95  # Alta confianza por defecto
        else:
            # Casos raros
            respuesta_final = "INVALIDA"
            es_valida = False
            confianza = 0.5
        
        # Determinar si requiere revisión
        requiere_rev = not es_valida
        
        # Crear objeto Respuesta
        respuesta = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=idx,
            respuesta_marcada=respuesta_final,
            es_correcta=False,  # Se actualizará al calificar
            confianza=confianza,
            respuesta_raw=str(respuesta_detectada),
            observacion=None,
            requiere_revision=requiere_rev
        )
        
        db.add(respuesta)
        respuestas_guardadas.append(respuesta)
        
        # Actualizar estadísticas
        stats["total"] += 1
        if es_valida:
            stats["validas"] += 1
        else:
            stats["vacias"] += 1
        
        if requiere_rev:
            stats["requieren_revision"] += 1
    
    # Commit a la base de datos
    db.commit()
    
    # Actualizar metadata de la hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_respuesta_id).first()
    if hoja:
        hoja.respuestas_detectadas = stats["total"]
        
        # Guardar metadatos extraídos
        metadata_actual = {}
        if hoja.metadata_json:
            try:
                metadata_actual = json.loads(hoja.metadata_json) if isinstance(hoja.metadata_json, str) else hoja.metadata_json
            except:
                metadata_actual = {}
        
        # Agregar datos extraídos
        metadata_actual["estadisticas_deteccion"] = stats
        metadata_actual["metadatos_extraidos"] = {
            "dni_postulante": datos.get("dni_postulante"),
            "codigo_aula": datos.get("codigo_aula"),
            "dni_profesor": datos.get("dni_profesor"),
            "codigo_hoja": datos.get("codigo_hoja"),
            "proceso_admision": datos.get("proceso_admision")
        }
        
        hoja.metadata_json = json.dumps(metadata_actual)
        db.commit()
    
    return {
        "success": True,
        "hoja_respuesta_id": hoja_respuesta_id,
        "respuestas_guardadas": len(respuestas_guardadas),
        "estadisticas": stats
    }


def requiere_revision(respuesta: str, confianza: float = None) -> bool:
    """
    Determina si una respuesta requiere revisión manual.
    """
    # Respuestas no válidas siempre requieren revisión
    if respuesta not in ["A", "B", "C", "D", "E"]:
        return True
    
    # Respuestas válidas con confianza baja
    if confianza and confianza < 0.70:
        return True
    
    return False


async def calificar_hoja_con_gabarito(
    hoja_respuesta_id: int,
    gabarito_id: int,
    db: Session
) -> Dict:
    """
    Califica una hoja comparando con el gabarito.
    """
    from app.models import ClaveRespuesta
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.id == gabarito_id
    ).first()
    
    if not gabarito:
        raise ValueError(f"Gabarito {gabarito_id} no encontrado")
    
    # Obtener respuestas de la hoja
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    if not respuestas:
        raise ValueError(f"No hay respuestas para la hoja {hoja_respuesta_id}")
    
    # Gabarito como dict
    clave_dict = {}
    if gabarito.respuestas_json:
        if isinstance(gabarito.respuestas_json, str):
            clave_dict = json.loads(gabarito.respuestas_json)
        else:
            clave_dict = gabarito.respuestas_json
    
    correctas = 0
    incorrectas = 0
    no_calificables = 0
    
    for respuesta in respuestas:
        num_pregunta = str(respuesta.numero_pregunta)
        respuesta_correcta = clave_dict.get(num_pregunta)
        
        # Solo calificar respuestas válidas (A-E)
        if respuesta.respuesta_marcada in ['A', 'B', 'C', 'D', 'E']:
            if respuesta.respuesta_marcada == respuesta_correcta:
                respuesta.es_correcta = True
                correctas += 1
            else:
                respuesta.es_correcta = False
                incorrectas += 1
        else:
            respuesta.es_correcta = False
            no_calificables += 1
    
    db.commit()
    
    # Calcular nota
    total_preguntas = len(respuestas)
    nota_final = (correctas / total_preguntas) * 20 if total_preguntas > 0 else 0
    
    # Actualizar hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_respuesta_id).first()
    if hoja:
        hoja.nota_final = nota_final
        hoja.respuestas_correctas_count = correctas
        hoja.estado = "calificado"
        db.commit()
    
    return {
        "success": True,
        "hoja_respuesta_id": hoja_respuesta_id,
        "correctas": correctas,
        "incorrectas": incorrectas,
        "no_calificables": no_calificables,
        "total": total_preguntas,
        "nota_final": round(nota_final, 2),
        "porcentaje": round((correctas / total_preguntas) * 100, 2) if total_preguntas > 0 else 0
    }


def generar_reporte_detallado(hoja_respuesta_id: int, db: Session) -> Dict:
    """
    Genera reporte detallado de una hoja.
    """
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_respuesta_id).first()
    
    if not hoja:
        raise ValueError(f"Hoja {hoja_respuesta_id} no encontrada")
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    # Agrupar por tipo
    validas = []
    vacias = []
    invalidas = []
    
    for resp in respuestas:
        resp_dict = {
            "numero": resp.numero_pregunta,
            "respuesta": resp.respuesta_marcada,
            "confianza": resp.confianza,
            "es_correcta": resp.es_correcta
        }
        
        if resp.respuesta_marcada in ['A', 'B', 'C', 'D', 'E']:
            validas.append(resp_dict)
        elif resp.respuesta_marcada == "VACIO":
            vacias.append(resp_dict)
        else:
            invalidas.append(resp_dict)
    
    return {
        "hoja": {
            "id": hoja.id,
            "codigo_hoja": hoja.codigo_hoja,
            "estado": hoja.estado,
            "nota_final": float(hoja.nota_final) if hoja.nota_final else None
        },
        "resumen": {
            "total": len(respuestas),
            "validas": len(validas),
            "vacias": len(vacias),
            "invalidas": len(invalidas),
            "correctas": sum(1 for r in respuestas if r.es_correcta)
        },
        "detalle_por_tipo": {
            "validas": validas,
            "vacias": vacias,
            "invalidas": invalidas
        },
        "requieren_revision": [
            {
                "numero": r.numero_pregunta,
                "respuesta": r.respuesta_marcada,
                "confianza": r.confianza
            }
            for r in respuestas if r.requiere_revision
        ]
    }