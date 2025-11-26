"""
Modelo de Log de Anulación de Hojas
app/models/log_anulacion.py

Registra todas las anulaciones y reimpresiones de hojas.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class LogAnulacionHoja(Base):
    """
    Registro de anulaciones de hojas de respuesta.
    
    Se usa cuando:
    - Se reimprime una hoja
    - Se anula una hoja por deterioro
    - Se anula por extravío
    - Se anula por error
    """
    
    __tablename__ = "log_anulacion_hojas"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Referencias
    hoja_respuesta_id = Column(Integer, ForeignKey('hojas_respuestas.id', ondelete='SET NULL'))
    postulante_id = Column(Integer, ForeignKey('postulantes.id', ondelete='CASCADE'), nullable=False)
    
    # Códigos
    codigo_hoja = Column(String(20), nullable=False, index=True)  # Código anulado
    nuevo_codigo_hoja = Column(String(20), index=True)  # Código nuevo (si se reimprimió)
    nueva_hoja_id = Column(Integer, ForeignKey('hojas_respuestas.id', ondelete='SET NULL'))
    
    # Motivo y tipo
    motivo = Column(Text, nullable=False)
    tipo_anulacion = Column(String(50), nullable=False)  # 'reimpresion', 'deterioro', 'extravio', 'error'
    
    # Responsable
    anulado_por = Column(String(100))
    cargo = Column(String(100))
    
    # Observaciones
    observaciones = Column(Text)
    
    # Timestamps
    fecha_anulacion = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relaciones
    hoja_respuesta = relationship("HojaRespuesta", foreign_keys=[hoja_respuesta_id], back_populates="logs_anulacion")
    postulante = relationship("Postulante", back_populates="logs_anulacion_hojas")
    
    def __repr__(self):
        return f"<LogAnulacionHoja(id={self.id}, codigo='{self.codigo_hoja}', tipo='{self.tipo_anulacion}')>"