from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class PostulanteAsignacion(Base):
    __tablename__ = "postulantes_asignacion"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Asignación
    aula_id = Column(Integer, ForeignKey("aulas.id"))
    profesor_id = Column(Integer, ForeignKey("profesores.id"))
    numero_asiento = Column(Integer)
    
    fecha_asignacion = Column(DateTime, default=datetime.now)
    
    # Relaciones
    postulante = relationship("Postulante", foreign_keys=[postulante_id])
    aula = relationship("Aula", foreign_keys=[aula_id])
    profesor = relationship("Profesor", foreign_keys=[profesor_id])