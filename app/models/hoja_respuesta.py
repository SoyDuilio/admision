"""
Modelo de Hoja de Respuesta
Almacena metadata sobre las fotos capturadas de las hojas de respuestas
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.sql import func

from app.database import Base
import enum


class EstadoProcesamiento(enum.Enum):
    generada = "generada"
    procesando = "procesando"
    completado = "completado"
    error = "error"
    observado = "observado"
    pendiente_calificar = "pendiente_calificar"


class APIVision(enum.Enum):
    """APIs de Vision disponibles"""
    google = "google"
    openai = "openai"
    anthropic = "anthropic"


class HojaRespuesta(Base):
    """
    Modelo de Hoja de Respuesta
    """
    
    __tablename__ = "hojas_respuestas"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey('postulantes.id', ondelete='CASCADE'), nullable=False)
    
    # Validación y códigos
    dni_profesor = Column(String(8), index=True)
    codigo_aula = Column(String(20), index=True)
    codigo_hoja = Column(String(20), unique=True, index=True)
    proceso_admision = Column(String(10), default="2025-2", index=True)
    
    # Imagen
    imagen_url = Column(String(500))
    imagen_original_nombre = Column(String(200))
    
    # Procesamiento
    api_utilizada = Column(String(20))
    estado = Column(String(20), default='procesando')
    respuestas_detectadas = Column(Integer, default=0)
    tiempo_procesamiento = Column(Float)
    metadata_json = Column(Text)
    
    # Calificación
    nota_final = Column(Float)
    respuestas_correctas_count = Column(Integer, default=0)
    
    # Observaciones
    observaciones = Column(Text)
    
    # Timestamps
    fecha_captura = Column(DateTime(timezone=True), server_default=func.now())
    fecha_calificacion = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ========================================================================
    # RELACIONES
    # ========================================================================
    postulante = relationship("Postulante", back_populates="hojas_respuestas")
    respuestas = relationship("Respuesta", back_populates="hoja_respuesta", cascade="all, delete-orphan")
    
    # ← AGREGAR ESTA LÍNEA:
    logs_anulacion = relationship("LogAnulacionHoja", foreign_keys="[LogAnulacionHoja.hoja_respuesta_id]", back_populates="hoja_respuesta")
    
    def __repr__(self):
        return f"<HojaRespuesta(id={self.id}, codigo_hoja='{self.codigo_hoja}', postulante_id={self.postulante_id}, estado='{self.estado}')>"
    
    @property
    def api_display(self) -> str:
        """Retorna el nombre amigable de la API usada"""
        api_names = {
            "google": "Google Vision",
            "openai": "OpenAI GPT-4 Vision",
            "anthropic": "Anthropic Claude Vision",
            "claude": "Anthropic Claude Vision"
        }
        return api_names.get(self.api_utilizada, self.api_utilizada or "N/A")
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "postulante_id": self.postulante_id,
            "codigo_hoja": self.codigo_hoja,
            "dni_profesor": self.dni_profesor,
            "codigo_aula": self.codigo_aula,
            "proceso_admision": self.proceso_admision,
            "imagen_url": self.imagen_url,
            "imagen_original_nombre": self.imagen_original_nombre,
            "api_utilizada": self.api_utilizada,
            "api_display": self.api_display,
            "estado": self.estado,
            "tiempo_procesamiento": self.tiempo_procesamiento,
            "respuestas_detectadas": self.respuestas_detectadas,
            "nota_final": self.nota_final,
            "respuestas_correctas_count": self.respuestas_correctas_count,
            "observaciones": self.observaciones,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "fecha_calificacion": self.fecha_calificacion.isoformat() if self.fecha_calificacion else None,
        }