# ============================================================================
# PROMPT MEJORADO V4 PARA DETECCIÓN DE RESPUESTAS
# app/services/prompt_vision_v4.py
# 
# CAMBIOS V4:
# - Instrucciones más estrictas para forzar JSON puro
# - Ejemplo completo del formato esperado
# - Énfasis en NO usar markdown
# ============================================================================

PROMPT_DETECCION_RESPUESTAS_V4 = """
Analiza la HOJA DE RESPUESTAS del Instituto I.S.T. Pedro A. Del Águila H.

DEBES RESPONDER *SOLO* EL SIGUIENTE JSON:

{
  "dni_postulante": "string",
  "codigo_aula": "string",
  "dni_profesor": "string",
  "codigo_hoja": "string",
  "proceso_admision": "string",
  "respuestas": ["A", "B", null, ... (100 elementos exactos)]
}

REGLAS ESTRICTAS:

1. Las únicas respuestas válidas son: A, B, C, D o E.
2. Si está en minúsculas → convertir a mayúsculas.
3. Si hay dos marcas en la misma casilla → null.
4. Si una casilla está en blanco → null.
5. Números, símbolos, figuras, tachones, sombras → null.
6. No inventar códigos: solo transcribir lo impreso si es legible.
7. Si un código no es legible → devuelve "" (cadena vacía).
8. Las respuestas deben ser EXACTAMENTE 100 valores.
9. No expliques nada: entrega solo JSON válido.

OPTIMIZACIÓN PARA FOTOS DE CELULAR:
- Corrige rotación, sombras y perspectiva automáticamente.
- Acepta baja iluminación si el texto es legible.
- Si hay duda entre dos casillas, devolver null.

Ahora analiza la imagen.
"""