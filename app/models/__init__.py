from app.models.postulante import Postulante
from app.models.hoja_respuesta import HojaRespuesta
from app.models.respuesta import Respuesta
from app.models.calificacion import Calificacion
from app.models.clave_respuesta import ClaveRespuesta
from app.models.profesor import Profesor
from app.models.aula import Aula

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class AsignacionExamen(Base):
    __tablename__ = "asignaciones_examen"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relaciones
    postulante_id = Column(Integer, ForeignKey("postulantes.id", ondelete="CASCADE"), nullable=False)
    aula_id = Column(Integer, ForeignKey("aulas.id", ondelete="RESTRICT"), nullable=False)
    
    # Proceso
    proceso_admision = Column(String(10), nullable=False, default="2025-2", index=True)
    
    # Metadata
    asignado_por = Column(String(50), nullable=False, default="automatico")
    asignado_por_usuario = Column(String(100), nullable=True)
    fecha_asignacion = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    
    # Observaciones
    observaciones = Column(Text, nullable=True)
    motivo_reasignacion = Column(Text, nullable=True)
    
    # Estado
    estado = Column(String(20), nullable=False, default="asignado", index=True)
    
    # Auditoría
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relaciones ORM
    postulante = relationship("Postulante", back_populates="asignacion")
    aula = relationship("Aula", back_populates="asignaciones")
    
    def __repr__(self):
        return f"<AsignacionExamen(postulante_id={self.postulante_id}, aula_id={self.aula_id}, proceso={self.proceso_admision})>"



__all__ = [
    "Postulante",
    "HojaRespuesta", 
    "Respuesta",
    "Calificacion",
    "ClaveRespuesta",
    "Profesor",
    "Aula",
     "AsignacionExamen",  # ← AGREGAR
]