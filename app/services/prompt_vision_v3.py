# ============================================================================
# PROMPT MEJORADO PARA DETECCIÓN DE RESPUESTAS
# app/services/prompt_vision_v3.py
# ============================================================================

PROMPT_DETECCION_RESPUESTAS_V3 = """
Analiza esta hoja de respuestas de examen con 100 preguntas.

Cada pregunta tiene opciones A, B, C, D, E.

CLASIFICACIÓN:
1. Si detectas A, B, C, D o E (mayúscula) → usa esa letra
2. Si detectas a, b, c, d o e (minúscula) → CONVIERTE a mayúscula (a→A, b→B, etc.)
3. Si la casilla está vacía → "VACIO"
4. Si detectas otra letra (F, G, etc.) → "LETRA_INVALIDA"
5. Si hay un símbolo o garabato → "GARABATO"
6. Si marcó 2 o más opciones → "MULTIPLE"

Responde SOLO con este JSON (sin texto adicional, sin markdown):

{
  "respuestas": [
    {"numero": 1, "respuesta": "A", "confianza": 0.95},
    {"numero": 2, "respuesta": "B", "confianza": 0.88},
    {"numero": 3, "respuesta": "VACIO", "confianza": null},
    {"numero": 4, "respuesta": "LETRA_INVALIDA", "confianza": 0.80},
    ... hasta 100
  ],
  "resumen": {
    "total": 100,
    "validas": 85,
    "vacias": 8,
    "letra_invalida": 4,
    "garabatos": 2,
    "multiple": 1
  }
}

IMPORTANTE: Las minúsculas a, b, c, d, e son VÁLIDAS. Conviértelas a mayúsculas.
"""