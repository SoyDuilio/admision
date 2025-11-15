"""
POSTULANDO - API Routers
app/api/__init__.py

Importa y exporta todos los routers modulares.
"""

from .pages import router as pages_router
from .generacion import router as generacion_router
from .captura import router as captura_router
from .gabarito import router as gabarito_router
from .calificacion import router as calificacion_router
from .resultados import router as resultados_router
from .revision import router as revision_router
from .asignacion import router as asignacion_router

__all__ = [
    "pages_router",
    "generacion_router",
    "captura_router",
    "gabarito_router",
    "calificacion_router",
    "resultados_router",
    "revision_router",
    "asignacion_router",
]