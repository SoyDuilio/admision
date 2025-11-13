"""
Servicio de procesamiento de imágenes con APIs de visión (Claude, Google, OpenAI)
"""

import anthropic
import google.generativeai as genai
from google.cloud import vision
from openai import OpenAI
import base64
import json
import os
from typing import Dict
import PIL.Image


async def extraer_con_claude(imagen_path: str) -> Dict:
    """Extrae datos con Claude Vision."""
    try:
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        ext = imagen_path.split(".")[-1].lower()
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        prompt = """Analiza esta hoja de respuestas de examen de admisión del I. S. T. Pedro A. Del Águila H.

ESTRUCTURA:

## CÓDIGOS (parte superior, en fila):
DNI-POSTULANTE | CÓD-AULA | DNI-PROFESOR | CÓD-HOJA

Encontrarás 4 códigos separados:
- DNI Postulante: 8 dígitos
- Código Aula: 4-5 caracteres alfanuméricos
- DNI Profesor: 8 dígitos
- Código Hoja: 9 caracteres alfanuméricos

## RESPUESTAS (100 preguntas numeradas 1-100):
Cada pregunta: N. (  )
Dentro del paréntesis puede haber: A, B, C, D, E (o vacío)

REGLAS:
1. EXACTAMENTE 100 elementos en "respuestas"
2. Si vacío → null
3. Si letra válida → MAYÚSCULA
4. Cualquier otro valor → null

RESPONDE SOLO JSON:
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-2",
  "respuestas": ["A", "B", null, "C", ...]
}

VALIDACIÓN: Array "respuestas" debe tener EXACTAMENTE 100 elementos."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        respuesta_texto = message.content[0].text.strip()
        
        # Limpiar JSON
        if respuesta_texto.startswith("```json"):
            respuesta_texto = respuesta_texto[7:]
        if respuesta_texto.startswith("```"):
            respuesta_texto = respuesta_texto[3:]
        if respuesta_texto.endswith("```"):
            respuesta_texto = respuesta_texto[:-3]
        respuesta_texto = respuesta_texto.strip()
        
        resultado = json.loads(respuesta_texto)
        
        # Validar y ajustar respuestas
        if len(resultado["respuestas"]) > 100:
            print(f"⚠️ Claude detectó {len(resultado['respuestas'])} respuestas, truncando a 100")
            resultado["respuestas"] = resultado["respuestas"][:100]
        elif len(resultado["respuestas"]) < 100:
            print(f"⚠️ Claude detectó {len(resultado['respuestas'])} respuestas, rellenando hasta 100")
            while len(resultado["respuestas"]) < 100:
                resultado["respuestas"].append(None)
        
        # Normalizar respuestas
        respuestas_validadas = []
        for resp in resultado["respuestas"]:
            if resp is None or resp == "":
                respuestas_validadas.append(None)
            elif isinstance(resp, str) and resp.strip().upper() in ["A", "B", "C", "D", "E"]:
                respuestas_validadas.append(resp.strip().upper())
            else:
                respuestas_validadas.append(None)
        
        resultado["respuestas"] = respuestas_validadas
        
        return {
            "success": True,
            "api": "claude",
            "datos": resultado,
            "tokens": message.usage.input_tokens + message.usage.output_tokens
        }
        
    except Exception as e:
        return {"success": False, "api": "claude", "error": str(e)}


async def extraer_con_google_vision(imagen_path: str) -> Dict:
    """Extrae datos con Google Vision + Gemini."""
    try:
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        # Procesar con Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')
        img = PIL.Image.open(imagen_path)
        
        prompt = """Analiza esta hoja del I. S. T. Pedro A. Del Águila H.

Extrae:
1. DNI Postulante (8 dígitos)
2. Código Aula (4-5 caracteres)
3. DNI Profesor (8 dígitos)
4. Código Hoja (9 caracteres)
5. 100 respuestas (A, B, C, D, E o null)

RESPONDE SOLO JSON:
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-2",
  "respuestas": ["A", null, ...]
}

CRÍTICO: 100 elementos en "respuestas"."""

        response = model.generate_content([prompt, img])
        resultado_texto = response.text.strip()
        
        # Limpiar JSON
        if resultado_texto.startswith("```json"):
            resultado_texto = resultado_texto[7:]
        if resultado_texto.startswith("```"):
            resultado_texto = resultado_texto[3:]
        if resultado_texto.endswith("```"):
            resultado_texto = resultado_texto[:-3]
        resultado_texto = resultado_texto.strip()
        
        resultado = json.loads(resultado_texto)
        
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"Google: {len(resultado['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "google",
            "datos": resultado
        }
        
    except Exception as e:
        return {"success": False, "api": "google", "error": str(e)}


async def extraer_con_openai(imagen_path: str) -> Dict:
    """Extrae datos con OpenAI GPT-4 Vision."""
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        prompt = """Analiza esta hoja del I. S. T. Pedro A. Del Águila H.

CÓDIGOS:
- DNI Postulante: 8 dígitos
- Código Aula: 4-5 caracteres
- DNI Profesor: 8 dígitos
- Código Hoja: 9 caracteres

RESPUESTAS: 100 preguntas (A, B, C, D, E o null)

RESPONDE SOLO JSON:
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-2",
  "respuestas": ["A", null, ...]
}

IMPORTANTE: 100 elementos exactos."""

        response = client.chat.completions.create(
            model="gpt-4o",  # Actualizado de gpt-4-vision-preview
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            }],
            max_tokens=4000,
            temperature=0
        )
        
        resultado_texto = response.choices[0].message.content.strip()
        
        # Limpiar JSON
        if resultado_texto.startswith("```json"):
            resultado_texto = resultado_texto[7:]
        if resultado_texto.startswith("```"):
            resultado_texto = resultado_texto[3:]
        if resultado_texto.endswith("```"):
            resultado_texto = resultado_texto[:-3]
        resultado_texto = resultado_texto.strip()
        
        resultado = json.loads(resultado_texto)
        
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"OpenAI: {len(resultado['respuestas'])} respuestas")
        
        return {
            "success": True,
            "api": "openai",
            "datos": resultado,
            "tokens": response.usage.total_tokens
        }
        
    except Exception as e:
        return {"success": False, "api": "openai", "error": str(e)}


async def procesar_con_api_seleccionada(imagen_path: str, api_preferida: str = None):
    """
    Procesa con la API seleccionada o con fallback automático.
    
    Args:
        imagen_path: Ruta de la imagen
        api_preferida: "anthropic", "google" o "openai"
        
    Returns:
        Dict con resultado
    """
    if not api_preferida:
        api_preferida = "openai"  # ← CAMBIO: OpenAI por defecto
    
    # Orden de prioridad
    if api_preferida == "openai":
        apis_orden = ["openai", "anthropic", "google"]  # ← OpenAI primero
    elif api_preferida == "anthropic":
        apis_orden = ["anthropic", "google", "openai"]
    elif api_preferida == "google":
        apis_orden = ["google", "anthropic", "openai"]
    else:
        apis_orden = ["openai", "anthropic", "google"]  # ← Por defecto OpenAI
    
    ultimo_error = None
    
    for api in apis_orden:
        try:
            print(f"🔄 Intentando con {api.upper()}...")
            
            if api == "anthropic":
                resultado = await extraer_con_claude(imagen_path)
            elif api == "google":
                resultado = await extraer_con_google_vision(imagen_path)
            elif api == "openai":
                resultado = await extraer_con_openai(imagen_path)
            else:
                continue
            
            if resultado["success"]:
                print(f"✅ Éxito con {api.upper()}")
                return resultado
            else:
                ultimo_error = resultado["error"]
                print(f"⚠️ Falló {api.upper()}: {ultimo_error}")
                
        except Exception as e:
            ultimo_error = str(e)
            print(f"⚠️ Error con {api.upper()}: {ultimo_error}")
    
    return {
        "success": False,
        "error": f"Todas las APIs fallaron. Último error: {ultimo_error}"
    }