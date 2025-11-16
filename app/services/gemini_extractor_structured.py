"""
Gemini Extractor con Schema Estructurado
Adaptado de TypeScript a Python usando la API de Gemini con response schema
"""

import os
import json
import base64
from typing import Dict, List, Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, content_types


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)


# ============================================================================
# SCHEMA DE RESPUESTA ESTRUCTURADO
# ============================================================================

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "object",
            "properties": {
                "dniPostulante": {
                    "type": "string",
                    "description": "DNI-POSTULANTE code"
                },
                "codAula": {
                    "type": "string",
                    "description": "COD-AULA code"
                },
                "dniProfesor": {
                    "type": "string",
                    "description": "DNI-PROFESOR code"
                },
                "codigoDeHoja": {
                    "type": "string",
                    "description": "CODIGO DE HOJA code"
                }
            },
            "required": ["dniPostulante", "codAula", "dniProfesor", "codigoDeHoja"]
        },
        "answers": {
            "type": "array",
            "description": "An array of 100 answers",
            "items": {
                "type": "object",
                "properties": {
                    "questionNumber": {
                        "type": "integer",
                        "description": "The question number from 1 to 100"
                    },
                    "answer": {
                        "type": "string",
                        "description": "The character in the box. Can be empty string if blank, or the symbol if not a letter."
                    }
                },
                "required": ["questionNumber", "answer"]
            }
        }
    },
    "required": ["codes", "answers"]
}


# ============================================================================
# PROMPT
# ============================================================================

EXTRACTION_PROMPT = """Analyze the provided image of a completed exam answer sheet.

Extract the following four codes: 'DNI-POSTULANTE', 'COD-AULA', 'DNI-PROFESOR', and 'CODIGO DE HOJA'.

Also, extract all 100 answers from the numbered boxes. The answer is the character or symbol written inside each box.

If a box is empty, the answer should be an empty string. If the mark is illegible, make the best guess or represent it as a symbol.

Return the data strictly in the specified JSON format. Ensure there are exactly 100 answer entries, from 1 to 100.

IMPORTANT:
- Look carefully at each numbered box
- Read handwritten letters precisely
- Valid answers are typically: A, B, C, D, E
- Empty boxes should have answer as empty string ""
- If you see any mark but can't determine the letter, use your best judgment
"""


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

async def extract_data_from_image_structured(imagen_path: str) -> Dict:
    """
    Extrae datos de la imagen usando Gemini con schema estructurado.
    
    Args:
        imagen_path: Ruta a la imagen de la hoja de respuestas
        
    Returns:
        Dict con la estructura:
        {
            "success": bool,
            "data": {
                "codes": {
                    "dniPostulante": str,
                    "codAula": str,
                    "dniProfesor": str,
                    "codigoDeHoja": str
                },
                "answers": [
                    {"questionNumber": 1, "answer": "A"},
                    {"questionNumber": 2, "answer": "B"},
                    ...
                ]
            },
            "error": str (opcional)
        }
    """
    
    try:
        print(f"\n{'='*70}")
        print("🤖 EXTRAYENDO CON GEMINI + SCHEMA ESTRUCTURADO")
        print(f"{'='*70}")
        print(f"📸 Imagen: {os.path.basename(imagen_path)}")
        
        # ====================================================================
        # PASO 1: Cargar y codificar imagen
        # ====================================================================
        
        with open(imagen_path, "rb") as f:
            image_data = f.read()
        
        # Detectar mime type
        ext = imagen_path.lower().split('.')[-1]
        mime_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp'
        }
        mime_type = mime_type_map.get(ext, 'image/jpeg')
        
        print(f"📄 Mime type: {mime_type}")
        print(f"📊 Tamaño: {len(image_data) / 1024:.1f} KB")
        
        # ====================================================================
        # PASO 2: Subir imagen a Gemini
        # ====================================================================
        
        print("📤 Subiendo imagen a Gemini...")
        uploaded_file = genai.upload_file(imagen_path)
        print(f"✅ Archivo subido: {uploaded_file.name}")
        
        # ====================================================================
        # PASO 3: Configurar modelo con schema
        # ====================================================================
        
        print("🔧 Configurando modelo gemini-2.0-flash-exp...")
        
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA
            )
        )
        
        # ====================================================================
        # PASO 4: Generar contenido
        # ====================================================================
        
        print("🚀 Enviando request a Gemini...")
        
        response = model.generate_content([
            uploaded_file,
            EXTRACTION_PROMPT
        ])
        
        print("✅ Respuesta recibida")
        
        # ====================================================================
        # PASO 5: Parsear respuesta
        # ====================================================================
        
        response_text = response.text.strip()
        
        print(f"\n📄 Respuesta (primeros 300 chars):")
        print(response_text[:300])
        
        parsed_data = json.loads(response_text)
        
        # ====================================================================
        # PASO 6: Validación básica
        # ====================================================================
        
        if "codes" not in parsed_data or "answers" not in parsed_data:
            raise ValueError("Invalid data structure: missing 'codes' or 'answers'")
        
        if len(parsed_data["answers"]) != 100:
            raise ValueError(
                f"Expected 100 answers, got {len(parsed_data['answers'])}"
            )
        
        # Validar que todos los números estén presentes (1-100)
        question_numbers = {ans["questionNumber"] for ans in parsed_data["answers"]}
        expected_numbers = set(range(1, 101))
        
        if question_numbers != expected_numbers:
            missing = expected_numbers - question_numbers
            extra = question_numbers - expected_numbers
            raise ValueError(
                f"Question numbers mismatch. Missing: {missing}, Extra: {extra}"
            )
        
        print(f"\n✅ Validación exitosa:")
        print(f"   - Códigos detectados: {len(parsed_data['codes'])}/4")
        print(f"   - Respuestas: {len(parsed_data['answers'])}/100")
        
        # Contar respuestas válidas
        valid_answers = sum(
            1 for ans in parsed_data["answers"] 
            if ans["answer"] and ans["answer"].strip() != ""
        )
        empty_answers = 100 - valid_answers
        
        print(f"   - Válidas: {valid_answers}")
        print(f"   - Vacías: {empty_answers}")
        
        print(f"\n📊 Códigos extraídos:")
        for key, value in parsed_data["codes"].items():
            print(f"   - {key}: {value}")
        
        # ====================================================================
        # PASO 7: Limpiar archivo temporal
        # ====================================================================
        
        try:
            genai.delete_file(uploaded_file.name)
            print(f"\n🗑️  Archivo temporal eliminado")
        except Exception as e:
            print(f"\n⚠️  No se pudo eliminar archivo temporal: {e}")
        
        print(f"\n{'='*70}")
        print("✅ EXTRACCIÓN COMPLETADA")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "data": parsed_data
        }
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response: {str(e)}"
        print(f"\n❌ ERROR: {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }
    
    except ValueError as e:
        error_msg = f"Validation error: {str(e)}"
        print(f"\n❌ ERROR: {error_msg}")
        return {
            "success": False,
            "error": error_msg
        }
    
    except Exception as e:
        error_msg = f"Failed to process image with Gemini: {str(e)}"
        print(f"\n❌ ERROR: {error_msg}")
        
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": error_msg
        }


# ============================================================================
# FUNCIÓN ADAPTADORA PARA FORMATO LEGACY
# ============================================================================

async def extract_data_compatible(imagen_path: str) -> Dict:
    """
    Versión compatible con el formato actual del sistema.
    
    Convierte de:
    {
        "codes": {...},
        "answers": [{"questionNumber": 1, "answer": "A"}, ...]
    }
    
    A:
    {
        "dni_postulante": "...",
        "codigo_aula": "...",
        "dni_profesor": "...",
        "codigo_hoja": "...",
        "respuestas": ["A", "B", null, "C", ...]
    }
    """
    
    result = await extract_data_from_image_structured(imagen_path)
    
    if not result["success"]:
        return result
    
    data = result["data"]
    
    # Convertir formato
    codes = data["codes"]
    answers_list = data["answers"]
    
    # Ordenar por questionNumber
    answers_list.sort(key=lambda x: x["questionNumber"])
    
    # Convertir a array simple
    respuestas = []
    for ans in answers_list:
        answer_text = ans["answer"].strip().upper()
        
        # Convertir vacío a None
        if not answer_text:
            respuestas.append(None)
        # Solo aceptar A-E
        elif answer_text in ['A', 'B', 'C', 'D', 'E']:
            respuestas.append(answer_text)
        else:
            # Cualquier otra cosa se trata como None
            respuestas.append(None)
    
    return {
        "success": True,
        "data": {
            "dni_postulante": codes.get("dniPostulante", ""),
            "codigo_aula": codes.get("codAula", ""),
            "dni_profesor": codes.get("dniProfesor", ""),
            "codigo_hoja": codes.get("codigoDeHoja", ""),
            "respuestas": respuestas
        },
        "api": "gemini-structured",
        "modelo": "gemini-2.0-flash-exp"
    }


# ============================================================================
# FUNCIÓN DE PRUEBA
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Probar con una imagen
        resultado = await extract_data_compatible("test_image.jpg")
        
        if resultado["success"]:
            print("\n✅ ÉXITO!")
            print(json.dumps(resultado["data"], indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ ERROR: {resultado['error']}")
    
    asyncio.run(test())