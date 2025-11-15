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
⚠️ INSTRUCCIÓN CRÍTICA ⚠️
Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido.
- NO uses markdown (```json o ```)
- NO agregues explicaciones antes o después
- Tu respuesta debe comenzar con { y terminar con }
- SOLO el JSON, nada más

==================================================
TAREA: Analiza esta hoja de respuestas de examen
==================================================

La hoja contiene 100 preguntas numeradas del 1 al 100.
Cada pregunta tiene opciones: A, B, C, D, E

REGLAS DE CLASIFICACIÓN:
1. Si detectas A, B, C, D o E (mayúscula) → usa esa letra exacta
2. Si detectas a, b, c, d o e (minúscula) → CONVIERTE a mayúscula (a→A, b→B, c→C, d→D, e→E)
3. Si la casilla está VACÍA (sin marca) → "VACIO"
4. Si detectas otra letra fuera del rango (F, G, H, etc.) → "LETRA_INVALIDA"
5. Si hay un símbolo, dibujo o garabato → "GARABATO"
6. Si marcó 2 o más opciones → "MULTIPLE"
7. Si no puedes leer con claridad → "ILEGIBLE"

==================================================
FORMATO DE RESPUESTA (copia este formato EXACTO)
==================================================

{
  "respuestas": [
    {"numero": 1, "respuesta": "A", "confianza": 0.95},
    {"numero": 2, "respuesta": "B", "confianza": 0.88},
    {"numero": 3, "respuesta": "C", "confianza": 0.92},
    {"numero": 4, "respuesta": "D", "confianza": 0.85},
    {"numero": 5, "respuesta": "E", "confianza": 0.90},
    {"numero": 6, "respuesta": "VACIO", "confianza": null},
    {"numero": 7, "respuesta": "A", "confianza": 0.87},
    ... continúa hasta el número 100 ...
    {"numero": 100, "respuesta": "E", "confianza": 0.91}
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

==================================================
VALIDACIONES IMPORTANTES
==================================================
✓ Debe haber EXACTAMENTE 100 objetos en el array "respuestas"
✓ Los números deben ir del 1 al 100 (sin saltos)
✓ Cada objeto debe tener: numero, respuesta, confianza
✓ La confianza va de 0.0 a 1.0 (o null para respuestas no válidas)
✓ Las minúsculas a,b,c,d,e son VÁLIDAS → conviértelas a mayúsculas

==================================================
⚠️ RECORDATORIO FINAL ⚠️
==================================================
Tu respuesta COMPLETA debe ser SOLO el objeto JSON.
No escribas nada antes del { ni después del }
No uses markdown. No des explicaciones.
"""


# ============================================================================
# PROMPT ALTERNATIVO MÁS CORTO (por si el largo causa problemas)
# ============================================================================

PROMPT_DETECCION_RESPUESTAS_V4_CORTO = """
RESPONDE SOLO CON JSON VÁLIDO. NO uses markdown. Tu respuesta debe comenzar con { y terminar con }.

Analiza esta hoja de 100 preguntas (opciones A, B, C, D, E).

CLASIFICACIÓN:
- A, B, C, D, E (mayúscula o minúscula) → letra en MAYÚSCULA
- Vacía → "VACIO"
- Otra letra (F, G, etc.) → "LETRA_INVALIDA"
- Símbolo/garabato → "GARABATO"
- Múltiples marcas → "MULTIPLE"
- No legible → "ILEGIBLE"

FORMATO:
{
  "respuestas": [
    {"numero": 1, "respuesta": "A", "confianza": 0.95},
    {"numero": 2, "respuesta": "B", "confianza": 0.88},
    ... (100 total)
  ],
  "resumen": {
    "total": 100,
    "validas": 85,
    "vacias": 10,
    "letra_invalida": 3,
    "garabatos": 1,
    "multiple": 1
  }
}

IMPORTANTE: 
- Exactamente 100 respuestas (1-100)
- Solo el JSON, sin explicaciones
- No uses ```json ni ```
"""