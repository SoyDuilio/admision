"""
Configuración de la base de datos
SQLAlchemy setup para PostgreSQL en Railway
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Crear engine de SQLAlchemy
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verifica conexiones antes de usarlas
    pool_recycle=3600,   # Recicla conexiones cada hora
    echo=settings.debug  # Log de queries SQL en modo debug
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base para los modelos
Base = declarative_base()


# Event listener para habilitar extensiones de PostgreSQL si es necesario
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Se ejecuta cuando se establece una nueva conexión"""
    logger.debug("Nueva conexión a la base de datos establecida")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para FastAPI
    Crea una sesión de BD para cada request y la cierra al terminar
    
    Uso:
        @app.get("/ejemplo")
        def ejemplo(db: Session = Depends(get_db)):
            # usar db aquí
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicializa la base de datos
    Crea todas las tablas si no existen
    """
    logger.info("Inicializando base de datos...")
    
    # Importar todos los modelos para que SQLAlchemy los conozca
    from app.models import postulante, hoja_respuesta, respuesta, clave_respuesta, calificacion
    
    # Crear todas las tablas
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ Base de datos inicializada correctamente")


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # ← Usar text()
        print("✅ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        print(f"❌ Error conectando a base de datos: {e}")
        return False


def drop_all_tables():
    """
    CUIDADO: Elimina todas las tablas
    Solo para desarrollo/testing
    """
    if not settings.debug:
        raise Exception("No se pueden eliminar tablas en modo producción")
    
    logger.warning("⚠️  ELIMINANDO TODAS LAS TABLAS...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("✅ Tablas eliminadas")


# Clase helper para transacciones
class DatabaseSession:
    """
    Context manager para manejar sesiones de BD
    
    Uso:
        with DatabaseSession() as db:
            postulante = db.query(Postulante).first()
    """
    
    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            logger.error(f"Error en transacción de BD: {exc_val}")
        self.db.close()