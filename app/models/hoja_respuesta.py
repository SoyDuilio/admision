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
    """Estados posibles del procesamiento"""
    procesando = "procesando"
    completado = "completado"
    error = "error"

class APIVision(enum.Enum):
    """APIs de Vision disponibles"""
    google = "google"
    openai = "openai"
    anthropic = "anthropic"


class HojaRespuesta(Base):
    """
    Modelo de Hoja de Respuesta
    
    Almacena la información sobre cada foto capturada:
    - Quién es el postulante
    - Dónde está guardada la imagen
    - Qué API se usó para procesarla
    - Tiempo de procesamiento
    - Estado del procesamiento
    """
    
    __tablename__ = "hojas_respuestas"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey('postulantes.id', ondelete='CASCADE'), nullable=False)
    
    # Imagen
    imagen_url = Column(String(500))
    imagen_original_nombre = Column(String(200))
    
    # Procesamiento
    api_utilizada = Column(String(20))  # 'google', 'openai', 'anthropic'
    estado = Column(String(20), default='procesando')  # 'procesando', 'completado', 'error'
    respuestas_detectadas = Column(Integer, default=0)
    tiempo_procesamiento = Column(Float)
    metadata_json = Column(Text)
    
    # Calificación
    nota_final = Column(Float)
    respuestas_correctas_count = Column(Integer, default=0)
    
    # Timestamps
    fecha_captura = Column(DateTime(timezone=True), server_default=func.now())
    fecha_calificacion = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    postulante = relationship("Postulante", back_populates="hojas_respuestas")
    respuestas = relationship("Respuesta", back_populates="hoja_respuesta", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HojaRespuesta(id={self.id}, postulante_id={self.postulante_id}, estado='{self.estado}')>"
    
    @property
    def estado(self) -> str:
        """Retorna el estado del procesamiento"""
        if self.error_message:
            return "error"
        elif self.procesada:
            return "procesada"
        else:
            return "pendiente"
    
    @property
    def api_display(self) -> str:
        """Retorna el nombre amigable de la API usada"""
        api_names = {
            "google": "Google Vision",
            "openai": "OpenAI GPT-4 Vision",
            "claude": "Anthropic Claude Vision"
        }
        return api_names.get(self.api_usada, self.api_usada or "N/A")
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "postulante_id": self.postulante_id,
            "imagen_path": self.imagen_path,
            "procesada": self.procesada,
            "api_usada": self.api_usada,
            "api_display": self.api_display,
            "tiempo_procesamiento": self.tiempo_procesamiento,
            "respuestas_detectadas": self.respuestas_detectadas,
            "confianza_promedio": self.confianza_promedio,
            "estado": self.estado,
            "gps_valido": self.gps_valido,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }