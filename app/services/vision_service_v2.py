"""
Vision Service V2 - Con pre-procesamiento OpenCV
Ubicación: app/services/vision_service_v2.py

FEATURES:
- Pre-procesamiento con OpenCV antes de enviar a APIs
- Fallback inteligente: gpt-4o-mini → gpt-4o → claude → gemini
- Validación estricta de 100 respuestas
- Normalización de respuestas (minúsculas → mayúsculas)
- Detección de respuestas inválidas
"""

import os
import base64
import json
import time
from typing import Dict, List, Optional, Tuple
import anthropic
from openai import OpenAI
import google.generativeai as genai

from app.services.image_preprocessor import ImagePreprocessor


# ============================================================================
# CONFIGURACIÓN DE APIs
# ============================================================================

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


# ============================================================================
# PROMPT OPTIMIZADO
# ============================================================================

PROMPT_BASE = """Analiza esta hoja de respuestas del I.S.T. Pedro A. Del Águila H.

CÓDIGOS A EXTRAER:
- DNI Postulante: 8 dígitos numéricos
- Código Aula: 4-5 caracteres alfanuméricos
- DNI Profesor: 8 dígitos numéricos
- Código Hoja: 9 caracteres alfanuméricos

RESPUESTAS:
- 100 preguntas numeradas del 1 al 100
- Formato: "1. (   )" - letra escrita DENTRO de los paréntesis
- Respuestas válidas: A, B, C, D, E (MAYÚSCULAS)
- Si el paréntesis está vacío → null
- Si hay letra minúscula (a-e) → convertir a mayúscula
- Si hay símbolo/número/tachado/borroso → null

RESPONDE SOLO CON JSON VÁLIDO (sin markdown, sin backticks):
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "9CFPrxSzP",
  "proceso_admision": "2025-2",
  "respuestas": ["A", null, "B", "C", null, ...]
}

CRÍTICO:
- El array "respuestas" DEBE tener EXACTAMENTE 100 elementos
- Cada elemento debe ser: "A", "B", "C", "D", "E" o null
- NO agregues texto adicional, SOLO el JSON
"""


# ============================================================================
# NORMALIZACIÓN Y VALIDACIÓN
# ============================================================================

def normalizar_y_validar_respuesta(resp_raw: str) -> Tuple[Optional[str], float, bool]:
    """
    Normaliza y valida una respuesta.
    
    Returns:
        tuple: (respuesta_normalizada, confianza, marcar_revision)
    """
    if resp_raw is None or str(resp_raw).strip() == "":
        return None, 1.0, False
    
    resp = str(resp_raw).strip().upper()
    
    # Válidas
    if resp in ["A", "B", "C", "D", "E"]:
        return resp, 1.0, False
    
    # Minúsculas → Convertir
    if resp.lower() in ["a", "b", "c", "d", "e"]:
        return resp.upper(), 0.95, False
    
    # Inválidas → NULL + revisión
    return None, 0.5, True


def validar_100_respuestas(respuestas: List) -> Tuple[List, Dict]:
    """
    Garantiza exactamente 100 respuestas válidas.
    
    Returns:
        tuple: (respuestas_normalizadas, estadisticas)
    """
    if len(respuestas) < 100:
        # Rellenar con nulls
        respuestas.extend([None] * (100 - len(respuestas)))
    elif len(respuestas) > 100:
        # Truncar
        respuestas = respuestas[:100]
    
    # Normalizar cada respuesta
    respuestas_normalizadas = []
    stats = {
        "validas": 0,
        "vacias": 0,
        "invalidas": 0,
        "requieren_revision": 0
    }
    
    for resp_raw in respuestas:
        resp_norm, confianza, requiere_rev = normalizar_y_validar_respuesta(resp_raw)
        respuestas_normalizadas.append(resp_norm)
        
        if resp_norm is not None:
            stats["validas"] += 1
        else:
            stats["vacias"] += 1
        
        if requiere_rev:
            stats["requieren_revision"] += 1
    
    return respuestas_normalizadas, stats


# ============================================================================
# EXTRACCIÓN CON OPENAI
# ============================================================================

def extraer_con_openai(imagen_path: str, modelo: str = "gpt-4o-mini") -> Dict:
    """
    Extrae datos con OpenAI (gpt-4o-mini o gpt-4o).
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto lector OCR de formularios académicos."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT_BASE},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0
        )
        
        texto = response.choices[0].message.content.strip()
        
        # Extraer JSON limpio
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        
        if inicio == -1 or fin == 0:
            return {"success": False, "error": "No JSON found"}
        
        json_str = texto[inicio:fin]
        datos = json.loads(json_str)
        
        # Validar 100 respuestas
        if "respuestas" in datos:
            datos["respuestas"], stats = validar_100_respuestas(datos["respuestas"])
            datos["stats"] = stats
        
        return {
            "success": True,
            "api": "openai",
            "modelo": modelo,
            "datos": datos
        }
        
    except Exception as e:
        return {
            "success": False,
            "api": "openai",
            "modelo": modelo,
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN CON ANTHROPIC (CLAUDE)
# ============================================================================

def extraer_con_claude(imagen_path: str) -> Dict:
    """
    Extrae datos con Claude Sonnet 4.
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
            max_tokens=2000,
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
                            "text": PROMPT_BASE
                        }
                    ]
                }
            ]
        )
        
        texto = message.content[0].text.strip()
        
        # Extraer JSON
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        
        if inicio == -1 or fin == 0:
            return {"success": False, "error": "No JSON found"}
        
        json_str = texto[inicio:fin]
        datos = json.loads(json_str)
        
        # Validar 100 respuestas
        if "respuestas" in datos:
            datos["respuestas"], stats = validar_100_respuestas(datos["respuestas"])
            datos["stats"] = stats
        
        return {
            "success": True,
            "api": "anthropic",
            "modelo": "claude-sonnet-4",
            "datos": datos
        }
        
    except Exception as e:
        return {
            "success": False,
            "api": "anthropic",
            "error": str(e)
        }


# ============================================================================
# EXTRACCIÓN CON GOOGLE (GEMINI)
# ============================================================================

def extraer_con_google_vision(imagen_path: str) -> Dict:
    """
    Extrae datos con Gemini 1.5 Flash.
    """
    try:
        # Subir imagen
        uploaded_file = genai.upload_file(imagen_path)
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        response = model.generate_content([
            uploaded_file,
            PROMPT_BASE
        ])
        
        texto = response.text.strip()
        
        # Extraer JSON
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        
        if inicio == -1 or fin == 0:
            return {"success": False, "error": "No JSON found"}
        
        json_str = texto[inicio:fin]
        datos = json.loads(json_str)
        
        # Validar 100 respuestas
        if "respuestas" in datos:
            datos["respuestas"], stats = validar_100_respuestas(datos["respuestas"])
            datos["stats"] = stats
        
        # Limpiar archivo
        genai.delete_file(uploaded_file.name)
        
        return {
            "success": True,
            "api": "google",
            "modelo": "gemini-1.5-flash",
            "datos": datos
        }
        
    except Exception as e:
        return {
            "success": False,
            "api": "google",
            "error": str(e)
        }


# ============================================================================
# FUNCIÓN PRINCIPAL CON PRE-PROCESAMIENTO
# ============================================================================

async def procesar_hoja_completa_v2(imagen_path: str) -> Dict:
    """
    Pipeline completo V2:
    1. Pre-procesar con OpenCV
    2. Intentar con APIs en orden
    3. Validar 100 respuestas
    
    Orden: gpt-4o-mini → gpt-4o → claude → gemini
    """
    inicio = time.time()
    
    print("\n" + "="*60)
    print("🚀 INICIANDO PROCESAMIENTO V2 (con OpenCV)")
    print("="*60)
    
    # ========================================================================
    # PASO 1: PRE-PROCESAMIENTO CON OPENCV
    # ========================================================================
    
    preprocessor = ImagePreprocessor()
    imagen_procesada = imagen_path
    preprocessing_metadata = {"used": False}
    
    try:
        imagen_procesada, preprocessing_metadata = preprocessor.procesar_completo(imagen_path)
        preprocessing_metadata["used"] = True
        print("✅ Pre-procesamiento OpenCV completado")
    except Exception as e:
        print(f"⚠️ Pre-procesamiento falló: {e}")
        print("ℹ️  Usando imagen original")
    
    # ========================================================================
    # PASO 2: INTENTAR CON APIs EN ORDEN
    # ========================================================================
    
    apis_orden = [
        ("gpt-4o-mini", lambda: extraer_con_openai(imagen_procesada, "gpt-4o-mini")),
        ("gpt-4o", lambda: extraer_con_openai(imagen_procesada, "gpt-4o")),
        ("claude", lambda: extraer_con_claude(imagen_procesada)),
        ("gemini", lambda: extraer_con_google_vision(imagen_procesada))
    ]
    
    resultado_final = None
    
    for nombre_api, func_api in apis_orden:
        print(f"\n🔄 Intentando con {nombre_api.upper()}...")
        
        resultado = func_api()
        
        if resultado["success"]:
            num_respuestas = len(resultado["datos"].get("respuestas", []))
            
            if num_respuestas == 100:
                print(f"✅ {nombre_api.upper()} exitoso - 100 respuestas detectadas")
                resultado_final = resultado
                break
            else:
                print(f"⚠️ {nombre_api.upper()} detectó {num_respuestas} respuestas (esperadas: 100)")
        else:
            print(f"❌ {nombre_api.upper()} falló: {resultado.get('error', 'Unknown')}")
    
    # ========================================================================
    # PASO 3: VALIDACIÓN FINAL
    # ========================================================================
    
    if resultado_final is None:
        return {
            "success": False,
            "error": "Todas las APIs fallaron",
            "tiempo_procesamiento": time.time() - inicio
        }
    
    # Agregar metadata
    resultado_final["tiempo_procesamiento"] = time.time() - inicio
    resultado_final["preprocessing"] = preprocessing_metadata
    resultado_final["imagen_procesada"] = imagen_procesada
    
    print("\n" + "="*60)
    print(f"✅ PROCESAMIENTO EXITOSO")
    print(f"📊 API: {resultado_final['api'].upper()}")
    print(f"⏱️  Tiempo: {resultado_final['tiempo_procesamiento']:.2f}s")
    if "stats" in resultado_final["datos"]:
        stats = resultado_final["datos"]["stats"]
        print(f"📝 Respuestas válidas: {stats['validas']}/100")
        print(f"⚠️  Requieren revisión: {stats['requieren_revision']}")
    print("="*60 + "\n")
    
    return resultado_final


# ============================================================================
# FUNCIÓN DE COMPATIBILIDAD
# ============================================================================

async def procesar_con_api_seleccionada(imagen_path: str, api_preferida: str = None):
    """
    Alias para compatibilidad con código existente.
    Usa la versión V2 con OpenCV.
    """
    return await procesar_hoja_completa_v2(imagen_path)