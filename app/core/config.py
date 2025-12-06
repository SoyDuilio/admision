"""
Configuración centralizada de la aplicación
Usa variables de entorno para datos sensibles
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Configuración de la aplicación usando Pydantic Settings
    """
    
    # ============================================================================
    # APLICACIÓN
    # ============================================================================
    
    APP_NAME: str = "POSTULANDO"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    
    # ============================================================================
    # BASE DE DATOS
    # ============================================================================
    
    # Railway PostgreSQL (Producción)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:oYIJXkEuPzFJShPYHPYBJGxbkgGGOKzz@nozomi.proxy.rlwy.net:32788/railway"
    )
    
    # Si Railway usa postgres:// en lugar de postgresql://
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    
    # ============================================================================
    # SEGURIDAD
    # ============================================================================
    
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "Dfxk3yDePruebaParaDemo1234567890"
    )
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    
    # ============================================================================
    # APIS EXTERNAS
    # ============================================================================
    
    # APIs Net PE (para validación de DNI)
    APIS_NET_PE_TOKEN: Optional[str] = os.getenv("APIS_NET_PE_TOKEN", None)
    
    # OpenAI (para Vision API - captura de hojas)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    
    # Anthropic Claude (alternativa para Vision)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    
    # Google Vision API
    GOOGLE_CLOUD_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_CLOUD_CREDENTIALS", None)
    
    # ============================================================================
    # ARCHIVOS Y STORAGE
    # ============================================================================
    
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv"}
    
    # ============================================================================
    # EMAIL (OPCIONAL)
    # ============================================================================
    
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    SMTP_FROM: Optional[str] = os.getenv("SMTP_FROM", None)
    
    # ============================================================================
    # CONFIGURACIÓN DE EXAMEN
    # ============================================================================
    
    # Número de preguntas por defecto
    TOTAL_PREGUNTAS: int = 50
    
    # Alternativas por pregunta
    ALTERNATIVAS: list = ["A", "B", "C", "D", "E"]
    
    # Nota mínima aprobatoria (se puede configurar por proceso)
    NOTA_MINIMA_DEFAULT: float = 10.5
    
    # ============================================================================
    # CORS (para desarrollo)
    # ============================================================================
    
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://admision.duilio.store"
    ]
    
    # ============================================================================
    # LOGS
    # ============================================================================
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # ============================================================================
    # CONFIGURACIÓN PYDANTIC
    # ============================================================================
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instancia global de configuración
settings = Settings()


# ============================================================================
# VALIDACIONES AL INICIAR
# ============================================================================

def validar_configuracion():
    """
    Valida que las configuraciones críticas estén presentes
    """
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Validar base de datos
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL no configurada")
        raise ValueError("DATABASE_URL es requerida")
    
    logger.info(f"✅ Base de datos configurada: {settings.DATABASE_URL[:30]}...")
    
    # Advertir sobre APIs faltantes (no crítico)
    if not settings.APIS_NET_PE_TOKEN:
        logger.warning("⚠️ APIS_NET_PE_TOKEN no configurada - validación de DNI deshabilitada")
    else:
        logger.info("✅ APIs Net PE configurada")
    
    if not settings.OPENAI_API_KEY:
        logger.warning("⚠️ OPENAI_API_KEY no configurada - OpenAI Vision deshabilitada")
    else:
        logger.info("✅ OpenAI API configurada")
    
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("⚠️ ANTHROPIC_API_KEY no configurada - Claude Vision deshabilitada")
    else:
        logger.info("✅ Anthropic API configurada")
    
    # Validar SECRET_KEY en producción
    if not settings.DEBUG and settings.SECRET_KEY == "tu-clave-secreta-super-segura-cambiar-en-produccion":
        logger.error("❌ SECRET_KEY debe cambiarse en producción")
        raise ValueError("SECRET_KEY insegura en producción")
    
    logger.info("✅ Configuración validada correctamente")


# Ejecutar validación al importar
if __name__ != "__main__":
    validar_configuracion()