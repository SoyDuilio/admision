"""
Modelo de Respuesta Individual
Almacena cada respuesta detectada (1-100) de cada postulante
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Respuesta(Base):
    """
    Modelo de Respuesta Individual
    
    Cada hoja de respuestas tiene 100 registros de este modelo
    Uno por cada pregunta del examen
    """
    
    __tablename__ = "respuestas"
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    hoja_respuesta_id = Column(Integer, ForeignKey("hojas_respuestas.id"), nullable=False, index=True)
    
    # Pregunta y respuesta
    numero_pregunta = Column(Integer, nullable=False)  # 1-100
    respuesta = Column(String(1), nullable=True)  # A, B, C, D, E, o null si está en blanco
    
    # Confianza del reconocimiento (0-1)
    confianza = Column(Float, nullable=True, default=1.0)
    
    # Validación
    es_correcta = Column(Boolean, nullable=True)  # Se llena después de calificar
    marcada_revision = Column(Boolean, default=False)  # Si requiere revisión manual
    
    # Información adicional (opcional)
    respuesta_alternativa = Column(String(1), nullable=True)  # Si la API detectó múltiples marcas
    
    # Relaciones
    hoja_respuesta = relationship("HojaRespuesta", back_populates="respuestas")
    
    def __repr__(self):
        return f"<Respuesta(pregunta={self.numero_pregunta}, respuesta={self.respuesta})>"
    
    @property
    def respuesta_display(self) -> str:
        """Retorna la respuesta en formato amigable"""
        if self.respuesta is None:
            return "EN BLANCO"
        elif self.respuesta == "?":
            return "NO LEGIBLE"
        else:
            return self.respuesta
    
    @property
    def estado_validacion(self) -> str:
        """Retorna el estado de validación"""
        if self.es_correcta is None:
            return "pendiente"
        elif self.es_correcta:
            return "correcta"
        else:
            return "incorrecta"
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "numero_pregunta": self.numero_pregunta,
            "respuesta": self.respuesta,
            "respuesta_display": self.respuesta_display,
            "confianza": self.confianza,
            "es_correcta": self.es_correcta,
            "marcada_revision": self.marcada_revision,
            "estado": self.estado_validacion
        }