import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configuración de la aplicación POSTULANDO
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Permite campos extra sin error
    )
    
    # ==============================================
    # APLICACIÓN
    # ==============================================
    app_name: str = "POSTULANDO Demo"
    environment: str = "demo"
    debug: bool = True
    secret_key: str = "change-me-in-production"
    port: int = 1010

    instituto_nombre: str = "Instituto Pedro A. Del Águila"
    instituto_logo: Optional[str] = None
    
    # ==============================================
    # BASE DE DATOS
    # ==============================================
    database_url: str
    
    # ==============================================
    # GOOGLE CLOUD VISION
    # ==============================================
    google_application_credentials: Optional[str] = None
    google_vision_api_key: Optional[str] = None
    google_credentials_json: Optional[str] = None  # Para Railway
    
    # ==============================================
    # OPENAI
    # ==============================================
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    
    # ==============================================
    # ANTHROPIC CLAUDE
    # ==============================================
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # ==============================================
    # CONFIGURACIÓN DE VISION APIs
    # ==============================================
    vision_primary: str = "google"  # "google", "openai", o "claude"
    vision_fallback_enabled: bool = True
    vision_timeout: int = 30  # segundos
    vision_retry_attempts: int = 2
    
    # ==============================================
    # DEMO
    # ==============================================
    demo_mode: bool = True
    demo_postulantes: int = 100
    
    # ==============================================
    # ARCHIVOS E IMÁGENES
    # ==============================================
    upload_dir: str = "./uploads"
    max_image_size_mb: int = 5
    allowed_image_types: list = ["image/jpeg", "image/png", "image/jpg"]
    
    # ==============================================
    # STORAGE (Para producción)
    # ==============================================
    storage_type: str = "local"  # "local", "s3", "gcs"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_region: str = "us-east-1"
    
    # ==============================================
    # CORS
    # ==============================================
    allowed_origins: list = ["http://localhost:3000", "http://localhost:8000", "http://localhost:1010", "http://localhost:5050"]


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton para obtener settings
    """
    return Settings()


def validate_vision_apis() -> dict:
    """
    Valida qué APIs de Vision están disponibles
    
    Returns:
        dict: Estado de cada API
        {
            "google": {"available": True, "configured": True},
            "openai": {"available": False, "configured": False},
            "claude": {"available": True, "configured": True}
        }
    """
    settings = get_settings()
    
    apis_status = {
        "google": {
            "available": False,
            "configured": bool(
                settings.google_application_credentials or 
                settings.google_vision_api_key or 
                settings.google_credentials_json
            )
        },
        "openai": {
            "available": False,
            "configured": bool(settings.openai_api_key)
        },
        "claude": {
            "available": False,
            "configured": bool(settings.anthropic_api_key)
        }
    }
    
    # Verificar si los módulos están instalados
    try:
        import google.cloud.vision
        apis_status["google"]["available"] = True
    except ImportError:
        pass
    
    try:
        import openai
        apis_status["openai"]["available"] = True
    except ImportError:
        pass
    
    try:
        import anthropic
        apis_status["claude"]["available"] = True
    except ImportError:
        pass
    
    return apis_status


def print_settings_summary():
    """
    Imprime un resumen de la configuración al iniciar
    """
    settings = get_settings()
    apis = validate_vision_apis()
    
    print("\n" + "="*60)
    print("⚙️  POSTULANDO - Configuración")
    print("="*60)
    
    print(f"\n📦 Aplicación:")
    print(f"  • Nombre: {settings.app_name}")
    print(f"  • Entorno: {settings.environment}")
    print(f"  • Debug: {settings.debug}")
    print(f"  • Puerto: {settings.port}")
    
    print(f"\n💾 Base de datos:")
    db_url = settings.database_url
    if "postgresql" in db_url:
        # Ocultar password en el print
        masked_url = db_url.split('@')[1] if '@' in db_url else db_url
        print(f"  • PostgreSQL: {masked_url}")
    else:
        print(f"  • {db_url[:50]}...")
    
    print(f"\n🤖 Vision APIs:")
    print(f"  • Primaria: {settings.vision_primary}")
    print(f"  • Fallback: {settings.vision_fallback_enabled}")
    
    for api_name, status in apis.items():
        icon = "✅" if (status["available"] and status["configured"]) else "❌"
        installed = "📦" if status["available"] else "❌"
        configured = "🔑" if status["configured"] else "❌"
        print(f"  {icon} {api_name.title()}: {installed} Instalado | {configured} Configurado")
    
    print(f"\n📁 Archivos:")
    print(f"  • Upload dir: {settings.upload_dir}")
    print(f"  • Max size: {settings.max_image_size_mb}MB")
    
    print("\n" + "="*60 + "\n")


# Instancia global
settings = get_settings()


# Si ejecutas este archivo directamente, muestra el resumen
if __name__ == "__main__":
    print_settings_summary()