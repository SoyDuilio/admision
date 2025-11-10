"""
Aplicación principal FastAPI - POSTULANDO DEMO
Punto de entrada de la aplicación
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings, validate_vision_apis
from app.database import init_db, check_db_connection

# Importar routers
from app.api import demo

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Eventos de startup y shutdown de la aplicación
    Se ejecuta al iniciar y al cerrar el servidor
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"🚀 Iniciando {settings.app_name}")
    logger.info("=" * 60)
    
    # Validar APIs de Vision
    try:
        validate_vision_apis()
    except ValueError as e:
        logger.error(str(e))
        raise
    
    # Verificar conexión a BD
    if not check_db_connection():
        logger.error("❌ No se pudo conectar a la base de datos")
        raise Exception("Database connection failed")
    
    # Inicializar tablas
    init_db()
    
    logger.info(f"✅ Servidor corriendo en http://0.0.0.0:{settings.port}")
    logger.info(f"✅ Modo: {settings.environment.upper()}")
    logger.info(f"✅ Debug: {settings.debug}")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("👋 Cerrando aplicación...")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Sistema de procesamiento automático de exámenes de admisión usando Vision APIs",
    version="1.0.0-demo",
    lifespan=lifespan,
    debug=settings.debug
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Incluir routers
app.include_router(demo.router, prefix="", tags=["Demo"])


# Ruta principal
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Página principal de la demo
    Muestra la interfaz de captura y procesamiento
    """
    return templates.TemplateResponse(
        "demo.html",
        {
            "request": request,
            "instituto": settings.instituto_nombre,
            "total_postulantes": settings.demo_postulantes
        }
    )


# Health check para Railway
@app.get("/health")
async def health_check():
    """
    Endpoint de health check
    Railway lo usa para verificar que la app está corriendo
    """
    db_status = check_db_connection()
    
    return {
        "status": "healthy" if db_status else "unhealthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": "connected" if db_status else "disconnected",
        "demo_mode": settings.demo_mode
    }


# Endpoint de información
@app.get("/info")
async def app_info():
    """Información sobre la aplicación y configuración"""
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode,
        "total_postulantes": settings.demo_postulantes,
        "instituto": settings.instituto_nombre,
        "vision_apis": {
            "google": bool(settings.google_vision_api_key or settings.google_application_credentials),
            "openai": bool(settings.openai_api_key),
            "claude": bool(settings.anthropic_api_key)
        }
    }


# Manejo de errores global
from fastapi import HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Manejo de excepciones HTTP"""
    logger.error(f"HTTP Error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Manejo de excepciones generales"""
    logger.error(f"Error no manejado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc) if settings.debug else "Internal server error"
        }
    )


# Middleware para logging de requests
from starlette.middleware.base import BaseHTTPMiddleware
from time import time

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging de todas las requests"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time()
        
        # Procesar request
        response = await call_next(request)
        
        # Calcular tiempo de procesamiento
        process_time = time() - start_time
        
        # Log
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response

# Agregar middleware
app.add_middleware(LoggingMiddleware)


# CORS (si necesitas acceder desde otro dominio)
from fastapi.middleware.cors import CORSMiddleware

if settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Ruta de prueba formal
@app.get("/prueba-formal", response_class=HTMLResponse)
async def prueba_formal(request: Request):
    return templates.TemplateResponse(
        "prueba_formal/demo_formal.html",
        {"request": request, "settings": settings, "fecha_actual": "2025"}
    )

@app.post("/api/procesar-examen")
async def procesar_examen(request: Request):
    data = await request.json()
    imagen_base64 = data.get('imagen')
    api_vision = data.get('api_vision', 'google')
    
    # Aquí va tu lógica existente de procesamiento
    # que ya tienes desde Admission-1 y Admission-2
    
    # Ejemplo de respuesta:
    return {
        "success": True,
        "codigos_verificados": "3/3",
        "respuestas_detectadas": 98,
        "mensaje": "Examen procesado correctamente"
    }
