"""
Modelo de Postulante
Representa a cada estudiante que rinde el examen
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Postulante(Base):
    """
    Modelo de Postulante
    
    Representa a cada estudiante inscrito para el examen de admisión
    Para la demo, se crearán 100 postulantes ficticios
    """
    
    __tablename__ = "postulantes"
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(8), unique=True, nullable=False, index=True)
    nombres = Column(String(100), nullable=False)
    apellido_paterno = Column(String(100), nullable=False)
    apellido_materno = Column(String(100), nullable=False)
    
    # Código único del postulante (formato: AULA-PUESTO-DNI)
    # Ejemplo: A01-P15-72345678
    codigo_unico = Column(String(20), unique=True)
    
    # Información adicional
    #email = Column(String(200), nullable=True)
    telefono = Column(String(15), nullable=True)
    programa_educativo = Column(String(200), nullable=True)  # Carrera a la que postula
    
    # Estado
    activo = Column(Boolean, default=True)
    examen_rendido = Column(Boolean, default=False)
    
    # Auditoría
    # Timestamps - usando func de SQLAlchemy (no deprecado)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    hojas_respuestas = relationship("HojaRespuesta", back_populates="postulante")
    calificaciones = relationship("Calificacion", back_populates="postulante")

    @property
    def nombre_completo(self):
        """Devuelve el nombre completo del postulante"""
        return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno}"
    
    def __repr__(self):
        return f"<Postulante(dni='{self.dni}', nombre='{self.nombre_completo}')>"
    
    @property
    def nombre_corto(self) -> str:
        """Retorna nombre y apellido paterno"""
        return f"{self.nombre} {self.apellido_paterno}"
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "dni": self.dni,
            "nombre_completo": self.nombre_completo,
            "codigo": self.codigo,
            "email": self.email,
            "telefono": self.telefono,
            "programa_estudio": self.programa_estudio,
            "examen_rendido": self.examen_rendido,
            "activo": self.activo,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }