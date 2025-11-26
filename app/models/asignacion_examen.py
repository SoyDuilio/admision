"""
Modelo de Asignación de Examen
app/models/asignacion_examen.py

Representa la asignación de un postulante a un aula con un profesor
para rendir el examen de admisión.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class AsignacionExamen(Base):
    """
    Asignación de postulante a aula para examen.
    
    Relaciones:
    - postulante → postulantes (CASCADE on delete)
    - aula → aulas (RESTRICT on delete)
    - profesor → profesores (NO ACTION on delete)
    
    Constraint único: (postulante_id, proceso_admision)
    Un postulante solo puede tener una asignación por proceso.
    """
    
    __tablename__ = "asignaciones_examen"
    
    # ========================================================================
    # CAMPOS PRINCIPALES
    # ========================================================================
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Referencias (Foreign Keys)
    postulante_id = Column(
        Integer, 
        ForeignKey('postulantes.id', ondelete='CASCADE'),
        nullable=False
    )
    
    aula_id = Column(
        Integer,
        ForeignKey('aulas.id', ondelete='RESTRICT'),
        nullable=False
    )
    
    profesor_id = Column(
        Integer,
        ForeignKey('profesores.id', ondelete='NO ACTION'),
        nullable=True
    )
    
    # Proceso y asignación
    proceso_admision = Column(String(10), default="2025-2", nullable=False)
    asignado_por = Column(String(50), default="automatico", nullable=False)
    asignado_por_usuario = Column(String(100), nullable=True)
    
    # Estado
    estado = Column(String(20), default="asignado", nullable=False)
    # Valores posibles: 'asignado', 'confirmado', 'cancelado', 'reasignado'
    
    # Observaciones
    observaciones = Column(Text, nullable=True)
    motivo_reasignacion = Column(Text, nullable=True)
    
    # ========================================================================
    # CAMPOS DE REIMPRESIÓN
    # ========================================================================
    
    hoja_original_devuelta = Column(Boolean, default=False, nullable=True)
    motivo_reimpresion = Column(Text, nullable=True)
    reimpresion_solicitada_por = Column(String(100), nullable=True)
    
    # ========================================================================
    # TIMESTAMPS
    # ========================================================================
    
    fecha_asignacion = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False
    )
    
    created_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # ========================================================================
    # RELACIONES
    # ========================================================================
    
    # Relación con Postulante (uno a uno)
    postulante = relationship(
        "Postulante",
        back_populates="asignacion_examen",
        foreign_keys=[postulante_id]
    )
    
    # Relación con Aula (muchos a uno)
    aula = relationship(
        "Aula",
        back_populates="asignaciones_examen",
        foreign_keys=[aula_id]
    )
    
    # Relación con Profesor (muchos a uno)
    profesor = relationship(
        "Profesor",
        back_populates="asignaciones_examen",
        foreign_keys=[profesor_id]
    )
    
    # ========================================================================
    # CONSTRAINTS Y ÍNDICES
    # ========================================================================
    
    __table_args__ = (
        # Constraint único: un postulante solo puede estar en un aula por proceso
        # Ya existe en la BD como 'uq_postulante_proceso'
        # Index implícito en postulante_id por foreign key
        # Index implícito en aula_id por foreign key
        # Index implícito en profesor_id por foreign key
    )
    
    def __repr__(self):
        return (
            f"<AsignacionExamen("
            f"id={self.id}, "
            f"postulante_id={self.postulante_id}, "
            f"aula_id={self.aula_id}, "
            f"estado='{self.estado}'"
            f")>"
        )