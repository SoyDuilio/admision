"""
POSTULANDO - Sistema de Exámenes de Admisión
app/main.py - VERSIÓN MODULARIZADA

Solo contiene:
- Configuración de FastAPI
- Registro de routers
- Health check
"""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from sqlalchemy.orm import Session
from app.database import get_db

from app.database import engine, Base
from app.config import settings

from app.api.documento_oficial import router as documento_router
from app.api.generar_hojas_aula import router as hojas_aula_router
from app.api.dashboard import router as dashboard_router
from app.api.generar_hoja_individual import router as hoja_individual_router

from app.api import reversion_asignaciones
from app.api import documento_oficial_gabarito
from app.api import generar_hojas_simple
from app.api import resultados_publicos

from app.routers import admin, api_coordinador


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

def format_number(value):
    """Formatear número con separador de miles"""
    try:
        return f"{int(value):,}".replace(",", ",")
    except (ValueError, TypeError):
        return value

def format_decimal(value, decimals=2):
    """Formatear decimal"""
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return value

def format_percentage(value, decimals=1):
    """Formatear porcentaje"""
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return value

templates.env.filters['format_number'] = format_number
templates.env.filters['format_decimal'] = format_decimal
templates.env.filters['format_percentage'] = format_percentage

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
# ============================================================================
# REGISTRO DE ROUTERS
# ============================================================================

# Generación de hojas
app.include_router(generacion_router, prefix="/api", tags=["Generación"])
app.include_router(hojas_aula_router, prefix="/api", tags=["Generación Hojas"])
app.include_router(hoja_individual_router, prefix="/api", tags=["Hojas Individual"])

# Gabarito
app.include_router(gabarito_router, prefix="/api", tags=["Gabarito"])
app.include_router(documento_oficial_gabarito.router, prefix="/api", tags=["Gabarito"])

# Captura y calificación
app.include_router(captura_router, prefix="/api", tags=["Captura"])
app.include_router(calificacion_router, prefix="/api", tags=["Calificación"])

# Resultados y revisión
app.include_router(resultados_router, prefix="/api", tags=["Resultados"])
app.include_router(revision_router, prefix="/api", tags=["Revisión"])

# Gestión y administración
app.include_router(reversion_asignaciones.router, prefix="/api", tags=["Gestión"])
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])

# Documentos oficiales
app.include_router(documento_router, prefix="/api", tags=["Documento Oficial"])

app.include_router(admin.router)
app.include_router(api_coordinador.router)

app.include_router(resultados_publicos.router, tags=["resultados"])
app.include_router(generar_hojas_simple.router, tags=["generacion"])
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
# PÁGINA DE GENERAR HOJAS SIMPLES
# ============================================================================

@app.get("/admin/generar-simple", response_class=HTMLResponse)
async def generar_simple_page(request: Request, db: Session = Depends(get_db)):
    from sqlalchemy import text
    
    # Contar postulantes por proceso
    query_count = text("""
        SELECT 
            proceso_admision,
            COUNT(*) as total
        FROM postulantes
        GROUP BY proceso_admision
        ORDER BY proceso_admision DESC
    """)
    
    procesos = db.execute(query_count).fetchall()
    
    # Crear dict con totales
    totales_por_proceso = {p.proceso_admision: p.total for p in procesos}
    
    return templates.TemplateResponse("admin/generar_simple.html", {
        "request": request,
        "totales_por_proceso": totales_por_proceso
    })

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