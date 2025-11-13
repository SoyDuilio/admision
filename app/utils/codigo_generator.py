"""
Generador de códigos únicos para hojas de respuestas
"""

import random
import string
from datetime import datetime
import uuid


def generar_codigo_hoja_unico():
    """
    Genera código alfanumérico de 9 caracteres sin caracteres confusos.
    
    Formato: 3 letras + 5 números + 1 letra
    Excluye: i, l, I, L, o, O, 0, 1
    
    Ejemplo: ABC23456D
    """
    letras_seguras = 'ABCDEFGHJKMNPQRSTUVWXYZ'  # Sin i, l, o
    numeros_seguros = '23456789'  # Sin 0, 1
    
    codigo = (
        ''.join(random.choices(letras_seguras, k=3)) +
        ''.join(random.choices(numeros_seguros, k=5)) +
        ''.join(random.choices(letras_seguras, k=1))
    )
    
    return codigo


def generar_codigo_unico_postulante(dni: str = None):
    """
    Genera código único para postulante (uso legacy)
    """
    fecha = datetime.now().strftime("%Y%m%d")
    uuid_short = str(uuid.uuid4())[:4].upper()
    
    if dni:
        return f"POST-{dni[-4:]}-{fecha}-{uuid_short}"
    else:
        return f"GEN-{fecha}-{uuid_short}"