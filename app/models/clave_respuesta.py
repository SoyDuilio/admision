"""
Modelo de Clave de Respuestas
Almacena las respuestas correctas del examen (1-100)
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from app.database import Base


class ClaveRespuesta(Base):
    """
    Modelo de Clave de Respuestas
    
    Almacena las 100 respuestas correctas del examen
    Se carga desde la foto del sobre lacrado con el gabarito oficial
    """
    
    __tablename__ = "clave_respuestas"
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    numero_pregunta = Column(Integer, unique=True, nullable=False, index=True)  # 1-100
    respuesta_correcta = Column(String(1), nullable=False)  # A, B, C, D, E
    
    # Metadata
    imagen_path = Column(String(500), nullable=True)  # Foto del gabarito original
    api_usada = Column(String(50), nullable=True)  # API que procesó la imagen
    
    # Información adicional (opcional)
    tema = Column(String(100), nullable=True)  # Matemática, Lenguaje, etc.
    dificultad = Column(String(20), nullable=True)  # fácil, medio, difícil
    observaciones = Column(Text, nullable=True)
    
    # Auditoría
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ClaveRespuesta(pregunta={self.numero_pregunta}, respuesta={self.respuesta_correcta})>"
    
    @property
    def pregunta_display(self) -> str:
        """Formato de pregunta para display"""
        return f"Pregunta {self.numero_pregunta}"
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "numero_pregunta": self.numero_pregunta,
            "respuesta_correcta": self.respuesta_correcta,
            "tema": self.tema,
            "dificultad": self.dificultad,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }