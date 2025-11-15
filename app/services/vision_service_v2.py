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

from sqlalchemy.orm import Session
from app.models import HojaRespuesta, Respuesta
from app.services.prompt_vision_v3 import PROMPT_DETECCION_RESPUESTAS_V3

from app.services.json_parser_robust import parsear_respuesta_vision_api

# ============================================================================
# CONFIGURACIÓN DE APIs
# ============================================================================

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


# ============================================================================
# PROMPT OPTIMIZADO
# ============================================================================

# Usar el nuevo prompt
PROMPT_BASE = PROMPT_DETECCION_RESPUESTAS_V3


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

# ============================================================================
# REEMPLAZAR: extraer_con_openai()
# ============================================================================

def extraer_con_openai(imagen_path: str, modelo: str = "gpt-4o-mini") -> Dict:
    """
    Extrae datos con OpenAI (gpt-4o-mini o gpt-4o).
    CON PARSING ROBUSTO.
    """
    try:
        with open(imagen_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        response = openai_client.chat.completions.create(
            model=modelo,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto lector OCR de formularios académicos. SOLO responde con JSON válido, sin markdown ni texto adicional."
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
        
        texto_raw = response.choices[0].message.content.strip()
        
        # USAR PARSER ROBUSTO
        datos = parsear_respuesta_vision_api(texto_raw)
        
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
# REEMPLAZAR: extraer_con_claude()
# ============================================================================

def extraer_con_claude(imagen_path: str) -> Dict:
    """
    Extrae datos con Claude Sonnet 4.
    CON PARSING ROBUSTO.
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
                            "text": PROMPT_BASE + "\n\nIMPORTANTE: Responde SOLO con el objeto JSON, sin explicaciones ni markdown."
                        }
                    ]
                }
            ]
        )
        
        texto_raw = message.content[0].text.strip()
        
        # USAR PARSER ROBUSTO
        datos = parsear_respuesta_vision_api(texto_raw)
        
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
# REEMPLAZAR: extraer_con_google_vision()
# ============================================================================

def extraer_con_google_vision(imagen_path: str) -> Dict:
    """
    Extrae datos con Gemini 1.5 Flash.
    CON PARSING ROBUSTO.
    """
    try:
        # Subir imagen
        uploaded_file = genai.upload_file(imagen_path)
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        response = model.generate_content([
            uploaded_file,
            PROMPT_BASE + "\n\nCRÍTICO: Tu respuesta DEBE ser ÚNICAMENTE el objeto JSON. NO uses markdown. NO agregues explicaciones."
        ])
        
        texto_raw = response.text.strip()
        
        # USAR PARSER ROBUSTO
        datos = parsear_respuesta_vision_api(texto_raw)
        
        # Validar 100 respuestas
        if "respuestas" in datos:
            datos["respuestas"], stats = validar_100_respuestas(datos["respuestas"])
            datos["stats"] = stats
        
        # Limpiar archivo
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass
        
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



# ============================================================================
# FUNCIONES CORREGIDAS PARA vision_service_v2.py
# Copia SOLO estas funciones al final de tu archivo
# ============================================================================

import json
from typing import Dict
from sqlalchemy.orm import Session


async def procesar_y_guardar_respuestas(
    hoja_respuesta_id: int,
    resultado_api: Dict,
    db: Session
) -> Dict:
    """
    Procesa el resultado de la Vision API y guarda cada respuesta en la BD.
    
    Args:
        hoja_respuesta_id: ID de la hoja de respuesta procesada
        resultado_api: Resultado JSON de la Vision API
        db: Sesión de base de datos
        
    Returns:
        Dict con estadísticas del procesamiento
    """
    
    from app.models import HojaRespuesta, Respuesta
    
    # Extraer respuestas del JSON
    respuestas_raw = resultado_api.get("respuestas", [])
    
    if not respuestas_raw:
        raise ValueError("No se encontraron respuestas en el resultado de la API")
    
    # Estadísticas
    stats = {
        "total": 0,
        "validas": 0,
        "vacias": 0,
        "letra_invalida": 0,
        "garabatos": 0,
        "multiple": 0,
        "ilegible": 0,
        "requieren_revision": 0
    }
    
    respuestas_guardadas = []
    
    for resp_data in respuestas_raw:
        numero = resp_data.get("numero")
        respuesta_detectada = resp_data.get("respuesta", "").upper()
        confianza = resp_data.get("confianza")
        observacion = resp_data.get("observacion")
        
        # Normalizar minúsculas a mayúsculas
        if respuesta_detectada.lower() in ['a', 'b', 'c', 'd', 'e']:
            respuesta_detectada = respuesta_detectada.upper()
        
        # Determinar si es válida
        es_valida = respuesta_detectada in ['A', 'B', 'C', 'D', 'E']
        
        # Determinar si requiere revisión
        requiere_rev = requiere_revision(respuesta_detectada, confianza)
        
        # Crear objeto Respuesta
        respuesta = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=numero,
            respuesta_marcada=respuesta_detectada,
            es_correcta=False,  # Se actualizará al calificar con gabarito
            confianza=confianza if es_valida else None,
            respuesta_raw=str(resp_data),  # Convertir a string directamente
            observacion=observacion,
            requiere_revision=requiere_rev
        )
        
        db.add(respuesta)
        respuestas_guardadas.append(respuesta)
        
        # Actualizar estadísticas
        stats["total"] += 1
        if es_valida:
            stats["validas"] += 1
        elif respuesta_detectada == "VACIO":
            stats["vacias"] += 1
        elif respuesta_detectada == "LETRA_INVALIDA":
            stats["letra_invalida"] += 1
        elif respuesta_detectada == "GARABATO":
            stats["garabatos"] += 1
        elif respuesta_detectada == "MULTIPLE":
            stats["multiple"] += 1
        elif respuesta_detectada == "ILEGIBLE":
            stats["ilegible"] += 1
        
        if respuesta.requiere_revision:
            stats["requieren_revision"] += 1
    
    # Commit a la base de datos
    db.commit()
    
    # Actualizar metadata de la hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_respuesta_id).first()
    if hoja:
        hoja.respuestas_detectadas = stats["total"]
        
        # Obtener metadata actual
        metadata_actual = {}
        if hoja.metadata_json:
            try:
                metadata_actual = json.loads(hoja.metadata_json) if isinstance(hoja.metadata_json, str) else hoja.metadata_json
            except:
                metadata_actual = {}
        
        # Agregar estadísticas
        metadata_actual["estadisticas_deteccion"] = stats
        
        # Guardar como string JSON
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
    
    Criterios:
    - Confianza < 0.7 en respuestas válidas
    - Todas las LETRA_INVALIDA
    - Todos los GARABATO
    - Todos los MULTIPLE
    - Todos los ILEGIBLE
    """
    
    # Respuestas problemáticas siempre requieren revisión
    if respuesta in ["LETRA_INVALIDA", "GARABATO", "MULTIPLE", "ILEGIBLE"]:
        return True
    
    # Respuestas válidas con confianza baja
    if respuesta in ["A", "B", "C", "D", "E"] and confianza and confianza < 0.70:
        return True
    
    return False


async def calificar_hoja_con_gabarito(
    hoja_respuesta_id: int,
    gabarito_id: int,
    db: Session
) -> Dict:
    """
    Califica una hoja de respuestas comparando con el gabarito.
    
    Args:
        hoja_respuesta_id: ID de la hoja a calificar
        gabarito_id: ID del gabarito (clave de respuestas)
        db: Sesión de base de datos
        
    Returns:
        Dict con resultados de la calificación
    """
    
    from app.models import ClaveRespuesta, HojaRespuesta, Respuesta
    
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
    
    # Gabarito como dict (numero_pregunta: respuesta_correcta)
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
            # No calificable (VACIO, LETRA_INVALIDA, etc.)
            respuesta.es_correcta = False
            no_calificables += 1
    
    db.commit()
    
    # Calcular nota (sobre 20)
    total_preguntas = len(respuestas)
    nota_final = (correctas / total_preguntas) * 20 if total_preguntas > 0 else 0
    
    # Actualizar hoja de respuestas
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
    Genera reporte detallado de una hoja con todas las estadísticas.
    
    Returns:
        Dict con información completa para mostrar al operador
    """
    
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_respuesta_id).first()
    
    if not hoja:
        raise ValueError(f"Hoja {hoja_respuesta_id} no encontrada")
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    # Agrupar por tipo
    por_tipo = {
        "validas": [],
        "vacias": [],
        "letra_invalida": [],
        "garabatos": [],
        "multiple": [],
        "ilegible": []
    }
    
    for resp in respuestas:
        if resp.es_valida:
            por_tipo["validas"].append(resp.to_dict())
        elif resp.respuesta_marcada == "VACIO":
            por_tipo["vacias"].append(resp.to_dict())
        elif resp.respuesta_marcada == "LETRA_INVALIDA":
            por_tipo["letra_invalida"].append(resp.to_dict())
        elif resp.respuesta_marcada == "GARABATO":
            por_tipo["garabatos"].append(resp.to_dict())
        elif resp.respuesta_marcada == "MULTIPLE":
            por_tipo["multiple"].append(resp.to_dict())
        elif resp.respuesta_marcada == "ILEGIBLE":
            por_tipo["ilegible"].append(resp.to_dict())
    
    return {
        "hoja": {
            "id": hoja.id,
            "codigo_hoja": hoja.codigo_hoja,
            "estado": hoja.estado,
            "nota_final": float(hoja.nota_final) if hoja.nota_final else None,
            "fecha_captura": hoja.fecha_captura.isoformat() if hoja.fecha_captura else None
        },
        "resumen": {
            "total": len(respuestas),
            "validas": len(por_tipo["validas"]),
            "vacias": len(por_tipo["vacias"]),
            "letra_invalida": len(por_tipo["letra_invalida"]),
            "garabatos": len(por_tipo["garabatos"]),
            "multiple": len(por_tipo["multiple"]),
            "ilegible": len(por_tipo["ilegible"]),
            "correctas": sum(1 for r in respuestas if r.es_correcta)
        },
        "detalle_por_tipo": por_tipo,
        "requieren_revision": [
            r.to_dict() for r in respuestas if r.requiere_revision
        ]
    }
