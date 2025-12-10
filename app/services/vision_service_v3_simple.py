"""
Vision Service V3 - SIMPLE usando Gemini 2.5 Flash
Usa schema estructurado para extracción precisa
"""
import os
import google.generativeai as genai
from typing import Dict, TypedDict, List
from pathlib import Path
import json
from app.services.gemini_extractor_structured import extract_data_compatible

# ============================================================================
# FUNCIÓN: Extraer DNI con zoom
# ============================================================================
async def extraer_dni_con_zoom(image_path: str) -> str:
    """
    Extrae SOLO el DNI con zoom a la zona superior de la hoja.
    Incluye limpieza robusta de JSON para evitar errores 'Here is...'.
    """
    from PIL import Image
    import json
    import re
    
    try:
        print(f"\n🔍 EXTRACCIÓN OPTIMIZADA DE DNI (con zoom)")
        print(f"{'='*70}")
        
        # 1. RECORTAR IMAGEN
        img = Image.open(image_path)
        width, height = img.size
        crop_height = int(height * 0.15)
        dni_zone = img.crop((0, 0, width, crop_height))
        
        temp_path = Path(image_path).parent / f"dni_zone_{Path(image_path).stem}.jpg"
        dni_zone.save(temp_path, "JPEG", quality=95)
        
        # 2. SUBIR
        print(f"📤 Subiendo zona DNI...")
        uploaded_file = genai.upload_file(path=str(temp_path), mime_type="image/jpeg")
        
        # 3. PROMPT ESTRICTO
        prompt = """Analyze this image crop.
        Find the DNI number (8 digits) inside the boxes.
        Return ONLY valid JSON. No Markdown. No introduction."""

        # 4. CONFIGURAR MODELO
        dni_schema = {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "object",
                    "properties": {
                        "dniPostulante": {
                            "type": "string",
                            "description": "8 digit number found in the boxes"
                        }
                    },
                    "required": ["dniPostulante"]
                }
            },
            "required": ["codes"]
        }
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=dni_schema,
            temperature=0.0, # Temperatura 0 para máxima precisión
        )
        
        # AÑADIMOS SYSTEM INSTRUCTION PARA FORZAR COMPORTAMIENTO ROBÓTICO
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            system_instruction="You are a strict JSON extraction engine. You never output conversational text. You output only raw JSON."
        )
        
        print(f"🚀 Enviando request...")
        response = model.generate_content([uploaded_file, prompt])
        
        # 5. PARSEAR CON LIMPIEZA (SANITIZACIÓN)
        print(f"📄 Respuesta cruda: {response.text[:100]}...")
        
        json_str = response.text
        
        # Lógica de limpieza: Encontrar el primer '{' y el último '}'
        # Esto elimina el "Here is the..." del principio y cualquier basura al final
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = json_str[start_idx : end_idx + 1]
        
        try:
            resultado = json.loads(json_str)
            dni = resultado.get("codes", {}).get("dniPostulante", "")
            
            # Limpieza adicional del valor (por si el modelo pone espacios o guiones)
            dni = re.sub(r'\D', '', dni) 
            
            print(f"✅ DNI Detectado: {dni}")
        except Exception as e:
            print(f"❌ Error al parsear JSON después de limpieza: {e}")
            dni = ""
        
        # 6. LIMPIAR ARCHIVOS
        try:
            genai.delete_file(uploaded_file.name)
            temp_path.unlink()
        except:
            pass
            
        return dni

    except Exception as e:
        print(f"❌ Error crítico en zoom: {e}")
        return ""


async def procesar_hoja_completa_v3(imagen_path: str) -> Dict:
    """
    Procesa hoja de respuestas con Gemini 2.5 Flash.
    Usa doble pasada: zoom en DNI + hoja completa para respuestas.
    """
    
    import google.generativeai as genai
    from pathlib import Path
    import json
    import os
    
    print(f"\n{'='*70}")
    print(f"🤖 EXTRAYENDO CON GEMINI + SCHEMA ESTRUCTURADO")
    print(f"{'='*70}")
    
    try:
         # ================================================================
        # 1. CONFIGURACIÓN GEMINI (UNA SOLA VEZ)
        # ================================================================
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "error": "GEMINI_API_KEY no configurada"
            }
        
        genai.configure(api_key=api_key)
        
        # ================================================================
        # 2. PRIMERA PASADA: ZOOM EN DNI (Alta precisión)
        # ================================================================
        
        print(f"\n🔍 PASO 1: Extrayendo DNI con zoom optimizado...")
        dni_optimizado = await extraer_dni_con_zoom(imagen_path)
        
        # ================================================================
        # 3. SEGUNDA PASADA: HOJA COMPLETA
        # ================================================================
        
        print(f"\n📸 PASO 2: Procesando hoja completa...")
        print(f"{'='*70}")
        print(f"📸 Imagen: {Path(imagen_path).name}")
        
        if not Path(imagen_path).exists():
            return {
                "success": False,
                "error": f"Archivo no encontrado: {imagen_path}"
            }
        
        file_size = Path(imagen_path).stat().st_size / 1024
        print(f"📄 Mime type: image/jpeg")
        print(f"📊 Tamaño: {file_size:.1f} KB")
        
        print(f"📤 Subiendo imagen a Gemini...")
        
        uploaded_file = genai.upload_file(
            path=imagen_path,
            mime_type="image/jpeg"
        )
        
        print(f"✅ Archivo subido: {uploaded_file.name}")
        
        # ================================================================
        # 4. SCHEMA DE RESPUESTA
        # ================================================================
        
        response_schema = {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "object",
                    "properties": {
                        "codigoDeHoja": {
                            "type": "string",
                            "description": "Código alfanumérico de la hoja"
                        }
                    },
                    "required": ["codigoDeHoja"]
                },
                "answers": {
                    "type": "array",
                    "description": "Lista de respuestas",
                    "items": {
                        "type": "object",
                        "properties": {
                            "questionNumber": {
                                "type": "integer"
                            },
                            "answer": {
                                "type": "string"
                            }
                        },
                        "required": ["questionNumber", "answer"]
                    }
                }
            },
            "required": ["codes", "answers"]
        }
        
        # ================================================================
        # 5. PROMPT
        # ================================================================
        
        prompt = """EXTRAE INFORMACIÓN DE ESTA HOJA DE RESPUESTAS.
1. CÓDIGO DE HOJA (Esquina superior derecha).
2. 100 RESPUESTAS (Marcas en rectángulos).
"""

        # ================================================================
        # 6. CONFIGURAR MODELO Y GENERAR
        # ================================================================
        
        print(f"🔧 Configurando modelo gemini-2.5-flash...")
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        
        print(f"🚀 Enviando request a Gemini...")
        
        response = model.generate_content([
            uploaded_file,
            prompt
        ])
        
        print(f"✅ Respuesta recibida")
        
        # ================================================================
        # 7. PARSEAR RESPUESTA
        # ================================================================
        
        try:
            resultado_json = json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback extremo si falla el JSON
            if "```json" in response.text:
                clean_text = response.text.split("```json")[1].split("```")[0]
                resultado_json = json.loads(clean_text)
            else:
                raise
        
        preview = response.text[:300] if len(response.text) > 300 else response.text
        print(f"📄 Respuesta (primeros 300 chars):")
        print(preview)
        
        # ================================================================
        # 8. EXTRAER Y VALIDAR DATOS
        # ================================================================
        
        codes = resultado_json.get("codes", {})
        answers = resultado_json.get("answers", [])
        
        codigo_hoja = codes.get("codigoDeHoja", "")
        dni_postulante = dni_optimizado if dni_optimizado else ""
        
        if len(answers) != 100:
            print(f"⚠️ Advertencia: Se recibieron {len(answers)} respuestas en lugar de 100")

        # Normalizar respuestas
        respuestas_normalizadas = []
        respuestas_validas = 0
        respuestas_vacias = 0
        
        # Aseguramos el orden 1-100 si vienen desordenadas o completamos
        mapa_respuestas = {item.get("questionNumber"): item.get("answer", "").strip().upper() for item in answers}
        
        for i in range(1, 101):
            respuesta = mapa_respuestas.get(i, "")
            if respuesta and respuesta not in ["A", "B", "C", "D", "E"]:
                respuesta = ""
            
            respuestas_normalizadas.append(respuesta)
            
            if respuesta:
                respuestas_validas += 1
            else:
                respuestas_vacias += 1
        
        # ================================================================
        # 9. VALIDACIÓN FINAL
        # ================================================================
        
        dni_valido = dni_postulante.isdigit() and len(dni_postulante) == 8
        
        print(f"✅ Validación exitosa:")
        print(f"   DNI (zoom): {dni_postulante} {'✅' if dni_valido else '⚠️'}")
        print(f"   Código hoja: {codigo_hoja}")
        print(f"   - Válidas: {respuestas_validas}")
        print(f"   - Vacías: {respuestas_vacias}")
        
        try:
            genai.delete_file(uploaded_file.name)
            print(f"🗑️  Archivo temporal eliminado")
        except:
            pass
        
        print(f"{'='*70}")
        print(f"✅ EXTRACCIÓN COMPLETADA")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "api": "gemini-structured",
            "modelo": "gemini-2.5-flash",
            "datos": {
                "dni_postulante": dni_postulante,
                "codigo_hoja": codigo_hoja,
                "respuestas": respuestas_normalizadas
            },
            "validaciones": {
                "dni_valido": dni_valido,
                "dni_longitud": len(dni_postulante),
                "dni_fuente": "zoom" if dni_optimizado else "hoja_completa",
                "respuestas_validas": respuestas_validas,
                "respuestas_vacias": respuestas_vacias
            }
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON hoja completa: {e}")
        return {
            "success": False,
            "error": f"Error JSON: {str(e)}"
        }
        
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# FUNCIONES AUXILIARES (mantener para compatibilidad)
# ============================================================================

async def procesar_y_guardar_respuestas(hoja_respuesta_id: int, resultado_api: Dict, db):
    """Guarda las 100 respuestas"""
    from app.models import Respuesta
    from datetime import datetime
    
    respuestas_array = resultado_api.get("respuestas", [])
    
    stats = {
        "validas": 0,
        "vacias": 0,
        "letra_invalida": 0,
        "requieren_revision": 0
    }
    
    for i, resp in enumerate(respuestas_array, 1):
        respuesta_upper = resp.strip().upper() if resp else ""
        
        if not respuesta_upper:
            stats["vacias"] += 1
        elif respuesta_upper in ['A', 'B', 'C', 'D', 'E']:
            stats["validas"] += 1
        else:
            stats["letra_invalida"] += 1
        
        respuesta_obj = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=i,
            respuesta_marcada=respuesta_upper if respuesta_upper else None,
            confianza=0.95,  # Gemini tiene alta confianza
            requiere_revision=(respuesta_upper not in ['A', 'B', 'C', 'D', 'E', '']),
            created_at=datetime.now()
        )
        
        db.add(respuesta_obj)
        
        if respuesta_upper and respuesta_upper not in ['A', 'B', 'C', 'D', 'E']:
            stats["requieren_revision"] += 1
    
    db.flush()
    
    return {
        "success": True,
        "estadisticas": stats
    }


async def calificar_hoja_con_gabarito(hoja_respuesta_id: int, gabarito_id: int, db):
    """Califica con gabarito"""
    from app.models import Respuesta, ClaveRespuesta
    from sqlalchemy import text
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.id == gabarito_id
    ).first()
    
    if not gabarito:
        raise Exception("Gabarito no disponible")
    
    query = text("""
        SELECT numero_pregunta, respuesta_correcta
        FROM clave_respuestas
        WHERE proceso_admision = :proceso
        ORDER BY numero_pregunta
    """)
    
    claves = db.execute(query, {"proceso": gabarito.proceso_admision}).fetchall()
    clave_dict = {str(c.numero_pregunta): c.respuesta_correcta.upper() for c in claves}
    
    correctas = 0
    incorrectas = 0
    no_calificables = 0
    
    for resp in respuestas:
        num = str(resp.numero_pregunta)
        respuesta_correcta = clave_dict.get(num, "").upper()
        respuesta_alumno = (resp.respuesta_marcada or "").upper()
        
        if not respuesta_alumno:
            no_calificables += 1
            resp.es_correcta = None
        elif respuesta_alumno == respuesta_correcta:
            correctas += 1
            resp.es_correcta = True
        else:
            incorrectas += 1
            resp.es_correcta = False
    
    nota_final = (correctas / 100) * 20
    porcentaje = (correctas / 100) * 100
    
    db.flush()
    
    return {
        "correctas": correctas,
        "incorrectas": incorrectas,
        "no_calificables": no_calificables,
        "nota_final": round(nota_final, 2),
        "porcentaje": round(porcentaje, 2)
    }


async def generar_reporte_detallado(*args, **kwargs):
    """Placeholder"""
    return {}