"""
POSTULANDO - Gemini Gabarito Extractor
app/services/gemini_gabarito_extractor.py

Extrae respuestas correctas del formato:
A => [números de preguntas]
B => [números de preguntas]
...
"""

import google.generativeai as genai
from typing import Dict, List, Optional
import json
import os
from datetime import datetime

# Configurar Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


# Schema estructurado para gabarito
GABARITO_SCHEMA = {
    "type": "object",
    "properties": {
        "respuestas_por_letra": {
            "type": "object",
            "description": "Preguntas agrupadas por respuesta correcta",
            "properties": {
                "A": {
                    "type": "object",
                    "properties": {
                        "preguntas": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Lista de números de pregunta cuya respuesta correcta es A"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total de preguntas con respuesta A"
                        }
                    },
                    "required": ["preguntas", "total"]
                },
                "B": {
                    "type": "object",
                    "properties": {
                        "preguntas": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Lista de números de pregunta cuya respuesta correcta es B"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total de preguntas con respuesta B"
                        }
                    },
                    "required": ["preguntas", "total"]
                },
                "C": {
                    "type": "object",
                    "properties": {
                        "preguntas": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Lista de números de pregunta cuya respuesta correcta es C"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total de preguntas con respuesta C"
                        }
                    },
                    "required": ["preguntas", "total"]
                },
                "D": {
                    "type": "object",
                    "properties": {
                        "preguntas": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Lista de números de pregunta cuya respuesta correcta es D"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total de preguntas con respuesta D"
                        }
                    },
                    "required": ["preguntas", "total"]
                },
                "E": {
                    "type": "object",
                    "properties": {
                        "preguntas": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Lista de números de pregunta cuya respuesta correcta es E"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total de preguntas con respuesta E"
                        }
                    },
                    "required": ["preguntas", "total"]
                }
            },
            "required": ["A", "B", "C", "D", "E"]
        },
        "total_general": {
            "type": "integer",
            "description": "Total de preguntas (debe ser 100)"
        },
        "validacion": {
            "type": "object",
            "properties": {
                "suma_correcta": {
                    "type": "boolean",
                    "description": "True si la suma de todas las respuestas es 100"
                },
                "mensaje": {
                    "type": "string",
                    "description": "Mensaje de validación"
                }
            }
        }
    },
    "required": ["respuestas_por_letra", "total_general", "validacion"]
}


async def extraer_gabarito_con_gemini(imagen_path: str) -> Dict:
    """
    Extrae el gabarito de una imagen usando Gemini 2.0 Flash.
    
    El formato esperado en la imagen es:
    A => 3, 5, 7, 12, 15, ...
    B => 2, 4, 6, 9, 11, ...
    C => 1, 8, 10, 13, ...
    D => 33, 42, 45, ...
    E => 81, 82, 83, ...
    
    Returns:
        Dict con respuestas_por_letra, totales y validación
    """
    
    try:
        print("\n" + "="*70)
        print("🤖 INICIANDO EXTRACCIÓN DE GABARITO CON GEMINI")
        print("="*70)
        
        # Cargar imagen
        with open(imagen_path, 'rb') as f:
            imagen_bytes = f.read()
        
        # Crear modelo con schema estructurado
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash-exp',
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": GABARITO_SCHEMA,
                "temperature": 0.1,  # Muy bajo para máxima precisión
            }
        )
        
        # Prompt optimizado
        prompt = """
Eres un experto en OCR para documentos de exámenes.

TAREA: Extraer las respuestas correctas de un GABARITO oficial de examen.

FORMATO ESPERADO EN LA IMAGEN:
```
A => [números de preguntas cuya respuesta correcta es A]
B => [números de preguntas cuya respuesta correcta es B]
C => [números de preguntas cuya respuesta correcta es C]
D => [números de preguntas cuya respuesta correcta es D]
E => [números de preguntas cuya respuesta correcta es E]

Total: [cantidad por letra]
```

INSTRUCCIONES CRÍTICAS:
1. Extrae TODOS los números de pregunta para cada letra (A, B, C, D, E)
2. Los números pueden estar separados por comas, espacios o saltos de línea
3. DEBE haber EXACTAMENTE 100 preguntas en total (1-100)
4. Cada pregunta debe aparecer UNA SOLA VEZ
5. Ordena los números de menor a mayor en cada lista
6. Calcula el total por cada letra
7. Valida que la suma total sea 100

EJEMPLO DE RESPUESTA ESPERADA:
```json
{
  "respuestas_por_letra": {
    "A": {
      "preguntas": [3, 5, 7, 12, 15, 18, ...],
      "total": 17
    },
    "B": {
      "preguntas": [2, 4, 6, 9, 11, ...],
      "total": 23
    },
    ...
  },
  "total_general": 100,
  "validacion": {
    "suma_correcta": true,
    "mensaje": "✅ Total correcto: 100 preguntas"
  }
}
```

CASOS ESPECIALES:
- Si un número es ilegible, NO lo incluyas
- Si faltan preguntas, indica en validacion.mensaje
- Si hay duplicados, reporta en validacion.mensaje
- Si la suma no es 100, marca suma_correcta como false

PROCESA LA IMAGEN Y EXTRAE LOS DATOS:
"""
        
        print("📤 Enviando imagen a Gemini...")
        inicio = datetime.now()
        
        # Enviar a Gemini
        response = model.generate_content([
            prompt,
            {
                "mime_type": "image/jpeg",
                "data": imagen_bytes
            }
        ])
        
        tiempo_procesamiento = (datetime.now() - inicio).total_seconds()
        print(f"⏱️  Tiempo de procesamiento: {tiempo_procesamiento:.2f}s")
        
        # Parsear respuesta
        resultado_raw = response.text
        print("\n📄 Respuesta raw de Gemini:")
        print(resultado_raw[:500] + "..." if len(resultado_raw) > 500 else resultado_raw)
        
        resultado = json.loads(resultado_raw)
        
        # Validar estructura
        if "respuestas_por_letra" not in resultado:
            raise ValueError("Respuesta sin estructura válida")
        
        # Validación adicional
        validacion = validar_gabarito(resultado)
        resultado["validacion_adicional"] = validacion
        
        print("\n" + "="*70)
        print("✅ EXTRACCIÓN COMPLETADA")
        print("="*70)
        print(f"Total A: {resultado['respuestas_por_letra']['A']['total']}")
        print(f"Total B: {resultado['respuestas_por_letra']['B']['total']}")
        print(f"Total C: {resultado['respuestas_por_letra']['C']['total']}")
        print(f"Total D: {resultado['respuestas_por_letra']['D']['total']}")
        print(f"Total E: {resultado['respuestas_por_letra']['E']['total']}")
        print(f"TOTAL GENERAL: {resultado['total_general']}")
        print("="*70)
        
        return {
            "success": True,
            "data": resultado,
            "tiempo_procesamiento": tiempo_procesamiento,
            "api_utilizada": "gemini-2.0-flash-exp"
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "tiempo_procesamiento": 0
        }


def validar_gabarito(resultado: Dict) -> Dict:
    """
    Validaciones adicionales del gabarito extraído.
    """
    
    validacion = {
        "errores": [],
        "advertencias": [],
        "es_valido": True
    }
    
    respuestas_por_letra = resultado.get("respuestas_por_letra", {})
    
    # Validar que estén todas las letras
    for letra in ['A', 'B', 'C', 'D', 'E']:
        if letra not in respuestas_por_letra:
            validacion["errores"].append(f"Falta letra {letra}")
            validacion["es_valido"] = False
    
    # Recolectar todas las preguntas
    todas_preguntas = []
    for letra in ['A', 'B', 'C', 'D', 'E']:
        if letra in respuestas_por_letra:
            preguntas = respuestas_por_letra[letra].get("preguntas", [])
            todas_preguntas.extend(preguntas)
    
    # Validar que sean 100 únicas
    if len(todas_preguntas) != 100:
        validacion["errores"].append(f"Total de preguntas: {len(todas_preguntas)} (esperado: 100)")
        validacion["es_valido"] = False
    
    # Validar que no haya duplicados
    if len(todas_preguntas) != len(set(todas_preguntas)):
        duplicados = [p for p in todas_preguntas if todas_preguntas.count(p) > 1]
        validacion["errores"].append(f"Preguntas duplicadas: {set(duplicados)}")
        validacion["es_valido"] = False
    
    # Validar que estén todas del 1 al 100
    preguntas_esperadas = set(range(1, 101))
    preguntas_encontradas = set(todas_preguntas)
    
    faltantes = preguntas_esperadas - preguntas_encontradas
    if faltantes:
        validacion["advertencias"].append(f"Preguntas faltantes: {sorted(faltantes)}")
        validacion["es_valido"] = False
    
    extras = preguntas_encontradas - preguntas_esperadas
    if extras:
        validacion["advertencias"].append(f"Números fuera de rango: {sorted(extras)}")
        validacion["es_valido"] = False
    
    return validacion


def convertir_a_array_100(respuestas_por_letra: Dict) -> List[str]:
    """
    Convierte el formato agrupado a un array de 100 respuestas [1-100].
    
    Entrada:
    {
        "A": {"preguntas": [3, 5, 7], ...},
        "B": {"preguntas": [1, 2, 4], ...},
        ...
    }
    
    Salida:
    ["B", "B", "A", "B", "A", "A", "A", ...]  # posiciones 1-100
    """
    
    respuestas_array = [""] * 100
    
    for letra in ['A', 'B', 'C', 'D', 'E']:
        if letra in respuestas_por_letra:
            preguntas = respuestas_por_letra[letra].get("preguntas", [])
            for num_pregunta in preguntas:
                if 1 <= num_pregunta <= 100:
                    respuestas_array[num_pregunta - 1] = letra
    
    return respuestas_array