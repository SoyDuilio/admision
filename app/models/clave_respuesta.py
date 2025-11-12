"""
Modelo de Clave de Respuestas (Gabarito)
Almacena las respuestas correctas del examen
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class ClaveRespuesta(Base):
    """
    Modelo de Clave de Respuestas
    
    Almacena el gabarito oficial del examen:
    - Número de pregunta (1-100)
    - Respuesta correcta (A, B, C, D, E)
    - Proceso de admisión
    """
    
    __tablename__ = "clave_respuestas"
    
    id = Column(Integer, primary_key=True, index=True)
    numero_pregunta = Column(Integer, nullable=False, index=True)
    respuesta_correcta = Column(String(1), nullable=False)
    
    # Proceso de admisión (NUEVO)
    proceso_admision = Column(String(10), default="2025-1", index=True)
    
    # Metadata opcional
    imagen_path = Column(String(500))
    api_usada = Column(String(50))
    tema = Column(String(100))
    dificultad = Column(String(20))
    observaciones = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ClaveRespuesta(pregunta={self.numero_pregunta}, correcta='{self.respuesta_correcta}', proceso='{self.proceso_admision}')>"
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "numero_pregunta": self.numero_pregunta,
            "respuesta_correcta": self.respuesta_correcta,
            "proceso_admision": self.proceso_admision,
            "tema": self.tema,
            "dificultad": self.dificultad,
            "observaciones": self.observaciones,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }