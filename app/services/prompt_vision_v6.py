# ============================================================================
# PROMPT V6 - ULTRA ESPECÍFICO PARA ESTRUCTURA DE 5 COLUMNAS
# app/services/prompt_vision_v6.py
# 
# CAMBIOS V6:
# - Descripción exacta de la estructura física de la hoja
# - Instrucciones detalladas sobre dónde buscar cada marca
# - Ejemplos de marcas válidas vs inválidas
# - Enfoque en detectar letras minúsculas dentro de paréntesis
# ============================================================================

PROMPT_PARTE_1_V6 = """
Analiza esta HOJA DE RESPUESTAS de examen de admisión del I.S.T. Pedro A. Del Águila H.

==================================================
ESTRUCTURA FÍSICA DE LA HOJA:
==================================================

La hoja tiene 100 preguntas organizadas en 5 COLUMNAS:
- COLUMNA 1: Preguntas 1-20
- COLUMNA 2: Preguntas 21-40
- COLUMNA 3: Preguntas 41-60
- COLUMNA 4: Preguntas 61-80
- COLUMNA 5: Preguntas 81-100

Cada pregunta tiene un PARÉNTESIS ( ) donde el estudiante escribe su respuesta.

==================================================
ENCABEZADO (METADATOS):
==================================================

En la parte superior de la hoja hay:
- DNI-POSTULANTE: número de 8 dígitos
- COD-AULA: código alfanumérico (ej: A101)
- DNI-PROFESOR: número de 8 dígitos
- CÓDIGO DE HOJA: secuencia alfanumérica (ej: UXJ545X)
- Proceso: año y período (ej: 2025-2)

Transcribe EXACTAMENTE lo que está impreso. Si no es legible → ""

==================================================
INSTRUCCIONES PARA DETECTAR RESPUESTAS (1-50):
==================================================

Solo analiza las PRIMERAS 50 PREGUNTAS (números 1 a 50).

DÓNDE BUSCAR:
- Dentro de los paréntesis ( )
- El estudiante escribe UNA LETRA dentro del paréntesis
- Busca letras MINÚSCULAS o MAYÚSCULAS

RESPUESTAS VÁLIDAS:
✓ a, b, c, d, e → Convertir a MAYÚSCULAS (A, B, C, D, E)
✓ A, B, C, D, E → Mantener como está

RESPUESTAS INVÁLIDAS (marca como null):
✗ ( ) vacío → null
✗ X, -, +, *, √, ÷, #, @, etc. → null (símbolos)
✗ Números (1, 2, 3, etc.) → null
✗ Garabatos o manchas → null
✗ Dos o más letras (ej: ab, AA) → null
✗ Letras fuera del rango (f, g, h, etc.) → null

==================================================
EJEMPLOS REALES:
==================================================

Pregunta 1: (X) → null (símbolo X, no es letra válida)
Pregunta 2: (b) → "B" (minúscula b → convertir a B)
Pregunta 3: (b) → "B"
Pregunta 7: (—) → null (guión, no es letra)
Pregunta 8: (C) → "C" (mayúscula válida)
Pregunta 9: (A) → "A"
Pregunta 10: (c) → "C"

==================================================
FORMATO DE RESPUESTA (JSON):
==================================================

{
  "dni_postulante": "79012345",
  "codigo_aula": "A101",
  "dni_profesor": "12345678",
  "codigo_hoja": "UXJ545X",
  "proceso_admision": "2025-2",
  "respuestas": ["B", "B", null, "C", "A", "C", ... (50 valores exactos)]
}

CRÍTICO:
- Tu respuesta DEBE ser SOLO este JSON
- NO uses markdown (```json)
- NO agregues explicaciones
- Debe comenzar con { y terminar con }
- Deben ser EXACTAMENTE 50 valores en el array "respuestas"

Ahora analiza la imagen cuidadosamente y extrae los datos.
"""


PROMPT_PARTE_2_V6 = """
Analiza esta HOJA DE RESPUESTAS de examen (continuación).

==================================================
ESTRUCTURA FÍSICA DE LA HOJA:
==================================================

La hoja tiene 100 preguntas en 5 COLUMNAS.
Solo analiza las ÚLTIMAS 50 PREGUNTAS (números 51 a 100).

Estas preguntas están en:
- COLUMNA 3: Preguntas 51-60
- COLUMNA 4: Preguntas 61-80
- COLUMNA 5: Preguntas 81-100

==================================================
INSTRUCCIONES PARA DETECTAR RESPUESTAS (51-100):
==================================================

DÓNDE BUSCAR:
- Dentro de los paréntesis ( ) de cada pregunta
- El estudiante escribe UNA LETRA dentro

RESPUESTAS VÁLIDAS:
✓ a, b, c, d, e → Convertir a MAYÚSCULAS (A, B, C, D, E)
✓ A, B, C, D, E → Mantener

RESPUESTAS INVÁLIDAS (marca como null):
✗ ( ) vacío → null
✗ Símbolos (X, -, +, *, √, etc.) → null
✗ Números → null
✗ Garabatos → null
✗ Múltiples letras → null
✗ Letras fuera de rango (f-z) → null

==================================================
EJEMPLOS:
==================================================

Pregunta 51: (b) → "B"
Pregunta 52: (D) → "D"
Pregunta 53: (A) → "A"
Pregunta 77: (X) → null
Pregunta 84: ( ) → null
Pregunta 92: ( ) → null

==================================================
FORMATO DE RESPUESTA:
==================================================

{
  "respuestas": ["B", "D", "A", null, "C", ... (50 valores exactos)]
}

CRÍTICO:
- Solo JSON válido
- NO markdown
- EXACTAMENTE 50 valores
- Tu respuesta debe comenzar con { y terminar con }

Analiza cuidadosamente las preguntas 51-100.
"""


# ============================================================================
# SUFIJOS POR API
# ============================================================================

SYSTEM_MESSAGE_OPENAI = """Eres un experto en OCR de formularios académicos manuscritos.
Tu única función es extraer datos de hojas de respuestas de exámenes.
Devuelves ÚNICAMENTE JSON válido, sin texto adicional, markdown ni explicaciones.
Tu respuesta DEBE comenzar con { y terminar con }."""

SUFFIX_CLAUDE = """

IMPORTANTE: 
- No incluyas <thinking> ni razonamiento interno
- Solo el JSON final
- Sin markdown
- Sin explicaciones adicionales"""

SUFFIX_GEMINI = """

CRÍTICO:
- Tu salida debe ser exclusivamente JSON válido
- NO utilices triple backtick (```json)
- NO agregues texto antes o después del JSON
- Responde SOLO con el objeto JSON"""