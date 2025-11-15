"""
JSON Parser Robusto para Vision APIs
app/services/json_parser_robust.py

PROBLEMA: Las Vision APIs a veces retornan JSON con:
- Markdown (```json ... ```)
- Comas faltantes
- Comentarios
- Trailing commas

SOLUCIÓN: Limpieza y corrección automática antes de parsear.
"""

import json
import re
from typing import Dict, Optional


def limpiar_markdown(texto: str) -> str:
    """
    Remueve markdown de bloques de código y caracteres invisibles.
    
    Ejemplos:
        ```json\n{...}\n``` → {...}
        ```\n{...}\n``` → {...}
        \ufeff{...} → {...}  (BOM)
    """
    # Limpiar BOM y caracteres invisibles
    texto = texto.strip().lstrip("\ufeff").lstrip("\u200b").lstrip("\u200c").lstrip("\u200d")
    
    # Remover ```json o ``` al inicio
    texto = re.sub(r'^```(?:json)?\s*\n?', '', texto.strip())
    
    # Remover ``` al final
    texto = re.sub(r'\n?```\s*$', '', texto.strip())
    
    return texto.strip()


def extraer_json_del_texto(texto: str) -> Optional[str]:
    """
    Extrae el primer objeto JSON válido del texto.
    
    Busca desde el primer { hasta el último } balanceado.
    """
    texto = texto.strip()
    
    inicio = texto.find("{")
    if inicio == -1:
        return None
    
    # Contar llaves para encontrar el cierre correcto
    contador = 0
    pos = inicio
    
    while pos < len(texto):
        if texto[pos] == '{':
            contador += 1
        elif texto[pos] == '}':
            contador -= 1
            
            if contador == 0:
                # Encontramos el cierre
                return texto[inicio:pos+1]
        
        pos += 1
    
    # No se encontró cierre balanceado
    return None


def corregir_comas_faltantes(json_str: str) -> str:
    """
    Intenta agregar comas faltantes entre elementos de arrays.
    
    Patrón común:
        {"numero": 1, "respuesta": "A"}
        {"numero": 2, "respuesta": "B"}  ← FALTA COMA
    
    Corrección:
        {"numero": 1, "respuesta": "A"},
        {"numero": 2, "respuesta": "B"}
    """
    # Buscar patrón: } seguido de { (sin coma entre ellos)
    # Permitir espacios y saltos de línea
    patron = r'\}\s*\n\s*\{'
    
    json_corregido = re.sub(patron, '},\n{', json_str)
    
    return json_corregido


def remover_trailing_commas(json_str: str) -> str:
    """
    Remueve comas sobrantes antes de ] o }.
    
    Ejemplos:
        [1, 2, 3,] → [1, 2, 3]
        {"a": 1,} → {"a": 1}
    """
    # Coma antes de ]
    json_str = re.sub(r',\s*\]', ']', json_str)
    
    # Coma antes de }
    json_str = re.sub(r',\s*\}', '}', json_str)
    
    return json_str


def remover_comentarios(json_str: str) -> str:
    """
    Remueve comentarios // y /* */ que algunas APIs agregan.
    """
    # Comentarios de línea //
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    
    # Comentarios de bloque /* */
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    return json_str


def parsear_json_robusto(texto_raw: str) -> Dict:
    """
    Parsea JSON de forma robusta aplicando múltiples técnicas de limpieza.
    
    Pasos:
    1. Limpiar markdown
    2. Extraer JSON del texto
    3. Remover comentarios
    4. Corregir comas faltantes
    5. Remover trailing commas
    6. Intentar parsear
    7. Si falla, intentar correcciones adicionales
    
    Args:
        texto_raw: Texto crudo que contiene JSON (posiblemente malformado)
        
    Returns:
        Dict parseado
        
    Raises:
        ValueError: Si no se pudo parsear después de todos los intentos
    """
    
    # Paso 1: Limpiar markdown
    texto = limpiar_markdown(texto_raw)
    
    # Paso 2: Extraer JSON
    json_str = extraer_json_del_texto(texto)
    
    if not json_str:
        raise ValueError("No se encontró un objeto JSON en el texto")
    
    # Paso 3: Remover comentarios
    json_str = remover_comentarios(json_str)
    
    # Paso 4: Corregir comas faltantes
    json_str = corregir_comas_faltantes(json_str)
    
    # Paso 5: Remover trailing commas
    json_str = remover_trailing_commas(json_str)
    
    # Intento 1: Parsear directamente
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️  Primer intento falló: {str(e)}")
        print(f"   Posición del error: línea {e.lineno}, columna {e.colno}")
    
    # Intento 2: Aplicar correcciones más agresivas
    try:
        # Reemplazar comillas simples por dobles (a veces las APIs usan ')
        json_str_corregido = json_str.replace("'", '"')
        
        return json.loads(json_str_corregido)
    except json.JSONDecodeError as e:
        print(f"⚠️  Segundo intento falló: {str(e)}")
    
    # Intento 3: Usar demjson3 (librería más permisiva) si está disponible
    try:
        import demjson3
        return demjson3.decode(json_str)
    except ImportError:
        # demjson3 no está instalado, continuar sin él
        pass
    except Exception as e:
        print(f"⚠️  demjson3 falló: {str(e)}")
    
    # Si llegamos aquí, no se pudo parsear
    # Guardar el JSON problemático para debugging
    print("\n" + "="*60)
    print("❌ JSON NO PUDO SER PARSEADO")
    print("="*60)
    print("Texto crudo (primeros 500 chars):")
    print(texto_raw[:500])
    print("\nJSON extraído (primeros 500 chars):")
    print(json_str[:500])
    print("="*60 + "\n")
    
    # Obtener el último error (de json.loads)
    ultimo_error = "Múltiples intentos de parsing fallaron"
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        ultimo_error = f"JSONDecodeError: {str(e)} en línea {e.lineno}, columna {e.colno}"
    
    raise ValueError(f"No se pudo parsear JSON después de múltiples intentos. {ultimo_error}")


def validar_estructura_respuestas(datos: Dict) -> bool:
    """
    Valida que el JSON parseado tenga la estructura esperada.
    
    Estructura esperada:
    {
        "respuestas": [
            {"numero": int, "respuesta": str, "confianza": float},
            ...
        ]
    }
    """
    if not isinstance(datos, dict):
        return False
    
    if "respuestas" not in datos:
        return False
    
    respuestas = datos["respuestas"]
    
    if not isinstance(respuestas, list):
        return False
    
    if len(respuestas) == 0:
        return False
    
    # Validar primer elemento como muestra
    primera = respuestas[0]
    
    if not isinstance(primera, dict):
        return False
    
    if "numero" not in primera or "respuesta" not in primera:
        return False
    
    return True


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def parsear_respuesta_vision_api(texto_raw: str) -> Dict:
    """
    Función principal para parsear respuestas de Vision APIs.
    
    Combina todas las técnicas de limpieza y validación.
    
    Args:
        texto_raw: Respuesta cruda de la Vision API
        
    Returns:
        Dict parseado (sin validación estricta de estructura)
        
    Raises:
        ValueError: Si no se pudo parsear
    """
    
    # Parsear con limpieza robusta
    datos = parsear_json_robusto(texto_raw)
    
    # NOTA: No validamos estructura aquí porque los formatos pueden variar
    # La validación específica se hace en cada servicio (vision_service_v3.py)
    
    return datos