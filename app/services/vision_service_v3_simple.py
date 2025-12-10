"""
Vision Service V3 - SIMPLE usando Gemini 2.5 Flash
Usa schema estructurado para extracción precisa
"""

import os
from typing import Dict
from app.services.gemini_extractor_structured import extract_data_compatible



async def extraer_dni_con_zoom(image_path: str) -> str:
    """
    Extrae SOLO el DNI con zoom a la zona superior de la hoja.
    Recorta la imagen a los primeros 15% de altura para mejor precisión.
    
    NOTA: Asume que genai ya está configurado.
    """
    from PIL import Image
    import google.generativeai as genai
    from pathlib import Path
    import json
    
    try:
        print(f"\n🔍 EXTRACCIÓN OPTIMIZADA DE DNI (con zoom)")
        print(f"{'='*70}")
        
        # ================================================================
        # 1. RECORTAR IMAGEN A ZONA DEL DNI
        # ================================================================
        
        # Abrir imagen original
        img = Image.open(image_path)
        width, height = img.size
        
        # Recortar solo el 15% superior (donde está el DNI)
        crop_height = int(height * 0.15)
        dni_zone = img.crop((0, 0, width, crop_height))
        
        # Guardar imagen recortada temporalmente
        temp_path = Path(image_path).parent / f"dni_zone_{Path(image_path).stem}.jpg"
        dni_zone.save(temp_path, "JPEG", quality=95)
        
        print(f"📐 Imagen original: {width}x{height}")
        print(f"✂️  Zona DNI recortada: {width}x{crop_height} (15% superior)")
        print(f"💾 Guardada en: {temp_path.name}")
        
        # ================================================================
        # 2. SUBIR IMAGEN RECORTADA A GEMINI
        # ================================================================
        
        print(f"📤 Subiendo zona DNI a Gemini...")
        
        uploaded_file = genai.upload_file(
            path=str(temp_path),
            mime_type="image/jpeg"
        )
        
        print(f"✅ Archivo subido: {uploaded_file.name}")
        
        # ================================================================
        # 3. SCHEMA SOLO PARA DNI
        # ================================================================
        
        response_schema = {
            "type": "object",
            "properties": {
                "dniPostulante": {
                    "type": "string",
                    "description": "DNI manuscrito del postulante (exactamente 8 dígitos)"
                }
            },
            "required": ["dniPostulante"]
        }
        
        # ================================================================
        # 4. PROMPT OPTIMIZADO SOLO PARA DNI
        # ================================================================
        
        prompt = """LEE EL DNI MANUSCRITO EN ESTA IMAGEN.

CONTEXTO:
Esta es la parte superior de una hoja de examen con el DNI escrito a mano en 8 rectángulos consecutivos.

ESTRATEGIA DE LECTURA:
1. Localiza los 8 rectángulos horizontales
2. Lee cada dígito de IZQUIERDA a DERECHA  
3. IDENTIFICA DÍGITOS REPETIDOS:
   - Busca dígitos que tengan la misma forma
   - Si el dígito 1 y el dígito 3 se ven IDÉNTICOS, son el mismo número
   - Si el dígito 1 y el dígito 3 son DIFERENTES, anota esa diferencia

4. DIFERENCIA ENTRE 4 Y 7:
   - El "4" tiene forma triangular con ángulo recto arriba
   - El "7" tiene forma de "L invertida" o puede tener línea horizontal en el medio
   - Si dudas entre 4 y 7, observa si hay OTROS dígitos iguales en el DNI

5. VALIDACIÓN CRUZADA:
   - DNI real: 73733606 tiene patrón: 7-3-7-3-3-6-0-6
   - Nota los dígitos repetidos en posiciones 1-3 (iguales), 2-4-5 (iguales), 6-8 (iguales)

REGLA DE ORO:
Si el primer dígito y el tercer dígito tienen LA MISMA FORMA MANUSCRITA, deben ser el mismo número.

Devuelve SOLO el DNI en formato JSON:
{
  "dniPostulante": "73733606"
}"""

        # ================================================================
        # 5. CONFIGURAR MODELO Y GENERAR
        # ================================================================
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.0,  # ← Temperatura a 0 para máxima precisión
            top_p=0.95,
            top_k=20,
            max_output_tokens=100,
        )
        
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=generation_config
        )
        
        print(f"🚀 Enviando request (solo DNI)...")
        
        response = model.generate_content([
            uploaded_file,
            prompt
        ])
        
        resultado = json.loads(response.text)
        dni = resultado.get("dniPostulante", "")
        
        print(f"✅ DNI detectado: {dni} ({len(dni)} dígitos)")
        
        # ================================================================
        # 6. LIMPIAR
        # ================================================================
        
        try:
            genai.delete_file(uploaded_file.name)
            temp_path.unlink()  # Eliminar imagen temporal
            print(f"🗑️  Archivos temporales eliminados")
        except Exception as e:
            print(f"⚠️  Error al limpiar: {e}")
        
        print(f"{'='*70}\n")
        
        return dni
        
    except Exception as e:
        print(f"❌ Error en extracción de DNI con zoom: {e}")
        import traceback
        traceback.print_exc()
        return ""


async def procesar_hoja_completa_v3(imagen_path: str) -> Dict:
    """
    Procesa hoja de respuestas con Gemini 2.0 Flash.
    Usa doble pasada: zoom en DNI + hoja completa para respuestas.
    
    ESTRATEGIA:
    1. Primera pasada: Zoom 15% superior para extraer DNI con alta precisión
    2. Segunda pasada: Hoja completa para código y 100 respuestas
    3. Combina resultados priorizando DNI de zoom
    """
    
    import google.generativeai as genai
    from pathlib import Path
    import json
    import os
    from datetime import datetime
    
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
        
        # Verificar archivo
        if not Path(imagen_path).exists():
            return {
                "success": False,
                "error": f"Archivo no encontrado: {imagen_path}"
            }
        
        # Info del archivo
        file_size = Path(imagen_path).stat().st_size / 1024
        print(f"📄 Mime type: image/jpeg")
        print(f"📊 Tamaño: {file_size:.1f} KB")
        
        # Subir imagen completa
        print(f"📤 Subiendo imagen a Gemini...")
        
        uploaded_file = genai.upload_file(
            path=imagen_path,
            mime_type="image/jpeg"
        )
        
        print(f"✅ Archivo subido: {uploaded_file.name}")
        
        # ================================================================
        # 4. SCHEMA DE RESPUESTA (solo código + respuestas)
        # ================================================================
        
        response_schema = {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "object",
                    "properties": {
                        "codigoDeHoja": {
                            "type": "string",
                            "description": "Código alfanumérico de la hoja (formato: 3 letras + 5 números + 1 letra)"
                        }
                    },
                    "required": ["codigoDeHoja"]
                },
                "answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "questionNumber": {
                                "type": "integer",
                                "description": "Número de pregunta (1-100)"
                            },
                            "answer": {
                                "type": "string",
                                "description": "Respuesta marcada: A, B, C, D, E o vacío"
                            }
                        },
                        "required": ["questionNumber", "answer"]
                    },
                    "minItems": 100,
                    "maxItems": 100
                }
            },
            "required": ["codes", "answers"]
        }
        
        # ================================================================
        # 5. PROMPT OPTIMIZADO (sin DNI)
        # ================================================================
        
        prompt = """EXTRAE INFORMACIÓN DE ESTA HOJA DE RESPUESTAS DE EXAMEN.

SECCIÓN 1: CÓDIGO DE HOJA

Ubicación: Esquina superior derecha
Formato: 3 letras MAYÚSCULAS + 5 números + 1 letra MAYÚSCULA
Ejemplo: "ABC12345D", "NEQ44946U", "XYZ98765K"
Este código está IMPRESO (no manuscrito)

SECCIÓN 2: RESPUESTAS (100 preguntas)

- 100 preguntas numeradas del 1 al 100
- Cada pregunta tiene 5 opciones: A, B, C, D, E
- Las respuestas se marcan en RECTÁNGULOS
- Instrucciones:
  * Busca marcas dentro de los rectángulos
  * Las marcas pueden ser: relleno, X, check, línea
  * Acepta mayúsculas (A,B,C,D,E) o minúsculas (a,b,c,d,e)
  * Convierte SIEMPRE a MAYÚSCULA
  * Si está vacío, devuelve cadena vacía ""
  * Si hay múltiples marcas, toma la más clara

FORMATO DE SALIDA:

{
  "codes": {
    "codigoDeHoja": "ABC12345D"
  },
  "answers": [
    {"questionNumber": 1, "answer": "A"},
    {"questionNumber": 2, "answer": "B"},
    {"questionNumber": 3, "answer": ""},
    ...
    {"questionNumber": 100, "answer": "E"}
  ]
}

Procesa la imagen y devuelve el JSON estructurado."""

        # ================================================================
        # 6. CONFIGURAR MODELO Y GENERAR
        # ================================================================
        
        print(f"🔧 Configurando modelo gemini-2.0-flash-exp...")
        
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )
        
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
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
        
        resultado_json = json.loads(response.text)
        
        # Preview
        preview = response.text[:300] if len(response.text) > 300 else response.text
        print(f"📄 Respuesta (primeros 300 chars):")
        print(preview)
        
        # ================================================================
        # 8. EXTRAER Y VALIDAR DATOS
        # ================================================================
        
        codes = resultado_json.get("codes", {})
        answers = resultado_json.get("answers", [])
        
        # Código de hoja
        codigo_hoja = codes.get("codigoDeHoja", "")
        
        # DNI: Priorizar el del zoom
        dni_postulante = dni_optimizado if dni_optimizado else ""
        
        # Validar cantidad de respuestas
        if len(answers) != 100:
            return {
                "success": False,
                "error": f"Se esperaban 100 respuestas, se recibieron {len(answers)}"
            }
        
        # Normalizar respuestas
        respuestas_normalizadas = []
        respuestas_validas = 0
        respuestas_vacias = 0
        
        for item in answers:
            respuesta = item.get("answer", "").strip().upper()
            
            # Validar A, B, C, D, E o vacío
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
        print(f"   DNI (zoom): {dni_postulante} ({len(dni_postulante)} dígitos) {'✅' if dni_valido else '⚠️'}")
        print(f"   Código hoja: {codigo_hoja}")
        print(f"   - Respuestas: {len(answers)}/100")
        print(f"   - Válidas: {respuestas_validas}")
        print(f"   - Vacías: {respuestas_vacias}")
        
        # ================================================================
        # 10. LIMPIAR ARCHIVOS TEMPORALES
        # ================================================================
        
        try:
            genai.delete_file(uploaded_file.name)
            print(f"🗑️  Archivo temporal eliminado")
        except Exception as e:
            print(f"⚠️  No se pudo eliminar archivo: {e}")
        
        print(f"{'='*70}")
        print(f"✅ EXTRACCIÓN COMPLETADA")
        print(f"{'='*70}\n")
        
        # ================================================================
        # 11. RETORNAR RESULTADO
        # ================================================================
        
        return {
            "success": True,
            "api": "gemini-structured",
            "modelo": "gemini-2.0-flash-exp",
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
        print(f"❌ Error al parsear JSON: {e}")
        return {
            "success": False,
            "error": f"Error al parsear respuesta JSON: {str(e)}"
        }
        
    except Exception as e:
        print(f"❌ Error en procesar_hoja_completa_v3: {e}")
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