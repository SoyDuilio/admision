"""
Modelo de Calificación
Almacena el resultado final de cada postulante después de comparar con la clave
"""

from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Calificacion(Base):
    """
    Modelo de Calificación
    
    Almacena el resultado final del examen de cada postulante:
    - Nota obtenida
    - Respuestas correctas/incorrectas
    - Estado (aprobado/desaprobado)
    - Orden de mérito
    """
    
    __tablename__ = "calificaciones"
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), nullable=False, unique=True, index=True)
    
    # Resultados
    nota = Column(Integer, nullable=False, index=True)  # 0-100
    correctas = Column(Integer, nullable=False, default=0)
    incorrectas = Column(Integer, nullable=False, default=0)
    en_blanco = Column(Integer, nullable=False, default=0)
    no_legibles = Column(Integer, nullable=False, default=0)
    
    # Porcentajes
    porcentaje_aciertos = Column(Float, nullable=True)  # 0-100
    
    # Estado
    aprobado = Column(Boolean, nullable=False, default=False, index=True)  # nota >= nota_minima
    nota_minima = Column(Integer, default=70)  # Nota mínima para aprobar
    
    # Orden de mérito
    puesto = Column(Integer, nullable=True, index=True)  # 1, 2, 3, etc.
    
    # Información adicional
    observaciones = Column(Text, nullable=True)
    requiere_revision = Column(Boolean, default=False)  # Si tiene muchas respuestas no legibles
    
    # Auditoría
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    calificado_at = Column(DateTime, nullable=True)
    
    # Relaciones
    postulante = relationship("Postulante", back_populates="calificaciones")
    
    def __repr__(self):
        return f"<Calificacion(postulante_id={self.postulante_id}, nota={self.nota}, puesto={self.puesto})>"
    
    @property
    def estado_display(self) -> str:
        """Retorna el estado en formato amigable"""
        if self.aprobado:
            return "APROBADO"
        else:
            return "DESAPROBADO"
    
    @property
    def nota_literal(self) -> str:
        """Retorna la nota en formato literal"""
        if self.nota >= 90:
            return "Excelente"
        elif self.nota >= 80:
            return "Muy Bueno"
        elif self.nota >= 70:
            return "Bueno"
        elif self.nota >= 60:
            return "Regular"
        else:
            return "Insuficiente"
    
    @property
    def color_nota(self) -> str:
        """Retorna el color según la nota para UI"""
        if self.aprobado:
            return "success"  # verde
        elif self.nota >= 60:
            return "warning"  # amarillo
        else:
            return "danger"  # rojo
    
    def calcular_porcentaje(self):
        """Calcula el porcentaje de aciertos"""
        total_respondidas = self.correctas + self.incorrectas
        if total_respondidas > 0:
            self.porcentaje_aciertos = (self.correctas / total_respondidas) * 100
        else:
            self.porcentaje_aciertos = 0.0
    
    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "postulante_id": self.postulante_id,
            "nota": self.nota,
            "correctas": self.correctas,
            "incorrectas": self.incorrectas,
            "en_blanco": self.en_blanco,
            "no_legibles": self.no_legibles,
            "porcentaje_aciertos": self.porcentaje_aciertos,
            "aprobado": self.aprobado,
            "estado": self.estado_display,
            "nota_literal": self.nota_literal,
            "puesto": self.puesto,
            "nota_minima": self.nota_minima,
            "requiere_revision": self.requiere_revision,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "calificado_at": self.calificado_at.isoformat() if self.calificado_at else None
        }