"""
Servicios de la aplicación POSTULANDO
Ubicación: app/services/__init__.py
"""

# GENERACIÓN DE PDFs
from app.services.pdf_generator_v3 import generar_hoja_respuestas_v3 as generar_hoja_respuestas_pdf

# PROCESAMIENTO DE IMÁGENES
from app.services.vision_service_v2 import (  # ← CAMBIO AQUÍ
    procesar_con_api_seleccionada,
    extraer_con_openai,
    extraer_con_claude,
    extraer_con_google_vision
)

#from app.services.image_preprocessor_v2 import ImagePreprocessorV2

# VALIDACIÓN Y CALIFICACIÓN
from app.services.validacion import validar_codigos
from app.services.calificacion import calcular_calificacion, gabarito_existe

__all__ = [
    'generar_hoja_respuestas_pdf',
    'procesar_con_api_seleccionada',
    'validar_codigos',
    'calcular_calificacion',
    'gabarito_existe',
    'ImagePreprocessor'
]