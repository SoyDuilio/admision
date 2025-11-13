"""
Utilidades del sistema
"""

from .codigo_generator import generar_codigo_hoja_unico, generar_codigo_unico_postulante
from .file_utils import guardar_foto_temporal, crear_directorio_capturas, crear_directorio_generadas

__all__ = [
    'generar_codigo_hoja_unico',
    'generar_codigo_unico_postulante',
    'guardar_foto_temporal',
    'crear_directorio_capturas',
    'crear_directorio_generadas'
]