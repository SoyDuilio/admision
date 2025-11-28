from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime, timezone

class Aula(Base):
    __tablename__ = "aulas"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100))
    pabellon = Column(String(10))
    piso = Column(String(5))
    numero = Column(String(10))
    capacidad = Column(Integer)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relaciones
    asignaciones = relationship("PostulanteAsignacion", back_populates="aula")
    asignaciones_examen = relationship("AsignacionExamen", back_populates="aula")
    postulantes = relationship("Postulante", back_populates="aula")

    
    def __repr__(self):
        return f"<Aula {self.codigo} - {self.nombre}>"