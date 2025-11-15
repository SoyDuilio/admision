# ============================================================================
# PROMPTS PARA PROCESAMIENTO DIVIDIDO
# app/services/prompt_vision_dividido.py
# 
# Estrategia: 2 requests paralelos
# - Request 1: Metadatos + Respuestas 1-50
# - Request 2: Respuestas 51-100
# ============================================================================

# ============================================================================
# PROMPT PARTE 1: METADATOS + PRIMERA MITAD (1-50)
# ============================================================================

PROMPT_PARTE_1_METADATOS_Y_PRIMERA_MITAD = """
Analiza la HOJA DE RESPUESTAS del Instituto I.S.T. Pedro A. Del Águila H.

DEBES RESPONDER *SOLO* EL SIGUIENTE JSON:

{
  "dni_postulante": "string",
  "codigo_aula": "string",
  "dni_profesor": "string",
  "codigo_hoja": "string",
  "proceso_admision": "string",
  "respuestas": ["A", "B", null, "C", ... (50 elementos: preguntas 1-50)]
}

INSTRUCCIONES:

METADATOS (impresos en la hoja):
- dni_postulante: Transcribe exactamente lo impreso
- codigo_aula: Transcribe exactamente lo impreso
- dni_profesor: Transcribe exactamente lo impreso
- codigo_hoja: Transcribe exactamente lo impreso
- proceso_admision: Transcribe exactamente lo impreso
- Si un campo NO es legible → "" (cadena vacía)

RESPUESTAS (solo preguntas 1 a 50):
- Solo analiza las PRIMERAS 50 PREGUNTAS (números 1-50)
- Valores válidos: "A", "B", "C", "D", "E" (MAYÚSCULAS)
- Si está en minúscula (a,b,c,d,e) → convertir a MAYÚSCULA
- Si está vacía → null
- Si hay 2+ marcas → null
- Si hay número, símbolo, garabato → null
- Deben ser EXACTAMENTE 50 valores en el array

FORMATO DE SALIDA:
- Solo JSON válido
- NO uses markdown (```json)
- NO agregues explicaciones
- Tu respuesta debe comenzar con { y terminar con }

Ahora analiza la imagen y devuelve SOLO el JSON.
"""


# ============================================================================
# PROMPT PARTE 2: SEGUNDA MITAD (51-100)
# ============================================================================

PROMPT_PARTE_2_SEGUNDA_MITAD = """
Analiza la HOJA DE RESPUESTAS del Instituto I.S.T. Pedro A. Del Águila H.

DEBES RESPONDER *SOLO* EL SIGUIENTE JSON:

{
  "respuestas": ["A", "B", null, "C", ... (50 elementos: preguntas 51-100)]
}

INSTRUCCIONES:

RESPUESTAS (solo preguntas 51 a 100):
- Solo analiza las ÚLTIMAS 50 PREGUNTAS (números 51-100)
- Valores válidos: "A", "B", "C", "D", "E" (MAYÚSCULAS)
- Si está en minúscula (a,b,c,d,e) → convertir a MAYÚSCULA
- Si está vacía → null
- Si hay 2+ marcas → null
- Si hay número, símbolo, garabato → null
- Deben ser EXACTAMENTE 50 valores en el array

FORMATO DE SALIDA:
- Solo JSON válido
- NO uses markdown (```json)
- NO agregues explicaciones
- Tu respuesta debe comenzar con { y terminar con }

Ahora analiza la imagen y devuelve SOLO el JSON.
"""


# ============================================================================
# SUFIJOS ESPECÍFICOS POR API
# ============================================================================

SYSTEM_MESSAGE_OPENAI = """Eres un extractor OCR extremadamente estricto. 
Devuelves únicamente JSON válido sin texto adicional, markdown ni explicaciones.
Tu respuesta DEBE comenzar con { y terminar con }."""

SUFFIX_CLAUDE = """

IMPORTANTE: No incluyas <thinking> ni ningún contenido interno de razonamiento.
Solo el JSON final. Sin markdown. Sin explicaciones."""

SUFFIX_GEMINI = """

Tu salida debe ser exclusivamente JSON válido.
NO utilices triple backtick (```json), HTML ni texto adicional.
Responde SOLO con el objeto JSON."""