"""
POSTULANDO - Sistema de Exámenes de Admisión
app/main.py - VERSIÓN MODULARIZADA

Solo contiene:
- Configuración de FastAPI
- Registro de routers
- Health check
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.database import engine, Base
from app.config import settings

from app.api.documento_oficial import router as documento_router
from app.api.generar_hojas_aula import router as hojas_aula_router
from app.api.dashboard import router as dashboard_router
from app.api.generar_hoja_individual import router as hoja_individual_router

# ============================================================================
# CREAR CARPETAS NECESARIAS
# ============================================================================

def crear_carpetas_necesarias():
    """Crea carpetas necesarias al iniciar la aplicación"""
    carpetas = [
        "temp_uploads",
        "temp_uploads/processed",
        "uploads/hojas_originales",
        "uploads/hojas_generadas",
        "uploads/reportes",
        "logs"
    ]
    
    for carpeta in carpetas:
        path = Path(carpeta)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Carpeta verificada: {carpeta}")

# Ejecutar al inicio
crear_carpetas_necesarias()

# ============================================================================
# CREAR TABLAS EN BD
# ============================================================================

Base.metadata.create_all(bind=engine)

# ============================================================================
# INICIALIZAR FASTAPI
# ============================================================================

app = FastAPI(
    title="POSTULANDO",
    description="Sistema de Exámenes de Admisión con Vision AI",
    version="2.0.0"
)

# ============================================================================
# MIDDLEWARE
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ARCHIVOS ESTÁTICOS
# ============================================================================

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ============================================================================
# TEMPLATES (Disponible para todos los routers)
# ============================================================================

templates = Jinja2Templates(directory="app/templates")

# ============================================================================
# IMPORTAR Y REGISTRAR ROUTERS
# ============================================================================

from app.api import (
    pages_router,
    generacion_router,
    captura_router,
    gabarito_router,
    calificacion_router,
    resultados_router,
    revision_router,
    asignacion_router
)

# Páginas HTML (sin prefijo /api)
app.include_router(pages_router)

# APIs (con prefijo /api y tags para documentación)
app.include_router(generacion_router, prefix="/api", tags=["Generación"])
app.include_router(captura_router, prefix="/api", tags=["Captura"])
app.include_router(gabarito_router, prefix="/api", tags=["Gabarito"])
app.include_router(calificacion_router, prefix="/api", tags=["Calificación"])
app.include_router(resultados_router, prefix="/api", tags=["Resultados"])
app.include_router(revision_router, prefix="/api", tags=["Revisión"])
app.include_router(asignacion_router, prefix="/api", tags=["Asignación"])
app.include_router(documento_router, prefix="/api", tags=["Documento Oficial"])
app.include_router(hojas_aula_router, prefix="/api", tags=["Generación Hojas"])
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
app.include_router(hoja_individual_router, prefix="/api", tags=["Hojas Individual"])

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check para Railway y monitoreo.
    Verifica conexión a BD.
    """
    from app.database import SessionLocal
    from app.models import Postulante
    
    db = SessionLocal()
    try:
        total_postulantes = db.query(Postulante).count()
        
        return {
            "status": "ok",
            "message": "POSTULANDO funcionando correctamente",
            "version": "2.0.0",
            "database": "connected",
            "postulantes": total_postulantes
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "database": "disconnected"
        }
    finally:
        db.close()

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True
    )