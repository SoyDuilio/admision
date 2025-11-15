# ============================================================================
# MODELOS SQLALCHEMY - TABLA RESPUESTAS CON CLASIFICACIÓN GRANULAR
# Agregar a app/models.py
# ============================================================================

from sqlalchemy import Column, Integer, String, Boolean, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class Respuesta(Base):
    """
    Modelo para almacenar cada respuesta individual de una hoja.
    
    CAMPOS PRINCIPALES:
    - respuesta_marcada: A, B, C, D, E, VACIO, LETRA_INVALIDA, GARABATO, MULTIPLE, ILEGIBLE
    - es_correcta: TRUE solo si respuesta_marcada in (A,B,C,D,E) Y coincide con gabarito
    - confianza: 0.0-1.0 para respuestas válidas, NULL para otros casos
    """
    
    __tablename__ = "respuestas"
    
    id = Column(Integer, primary_key=True, index=True)
    hoja_respuesta_id = Column(Integer, ForeignKey("hojas_respuestas.id"), nullable=False, index=True)
    numero_pregunta = Column(Integer, nullable=False)  # 1-100
    
    # VALORES POSIBLES:
    # 'A', 'B', 'C', 'D', 'E'           → Respuestas válidas (calificables)
    # 'VACIO'                            → Casilla sin marcar
    # 'LETRA_INVALIDA'                   → Letra fuera de A-E (F, G, etc.)
    # 'GARABATO'                         → Símbolos, borrones, trazos
    # 'MULTIPLE'                         → Marcó 2+ opciones
    # 'ILEGIBLE'                         → Marca presente pero no reconocible
    respuesta_marcada = Column(String(20), nullable=False)
    
    # TRUE/1: Solo si respuesta_marcada in ('A','B','C','D','E') Y coincide con gabarito
    # FALSE/0: Cualquier otro caso
    es_correcta = Column(Boolean, nullable=False, default=False)
    
    # Nivel de confianza de la detección (0.0-1.0)
    # NULL para respuestas no válidas (VACIO, LETRA_INVALIDA, etc.)
    confianza = Column(Numeric(3, 2), nullable=True)
    
    # Lo que detectó la API sin procesar (para debugging)
    respuesta_raw = Column(String(50), nullable=True)
    
    # Observaciones adicionales (ej: "Detectada letra F", "Marca borrosa")
    observacion = Column(Text, nullable=True)
    
    # Flag para revisión manual
    requiere_revision = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relación con hoja de respuestas
    hoja_respuesta = relationship("HojaRespuesta", back_populates="respuestas")
    
    def __repr__(self):
        return f"<Respuesta #{self.numero_pregunta}: {self.respuesta_marcada} (correcta={self.es_correcta})>"
    
    def to_dict(self):
        """Convierte a diccionario para serialización JSON."""
        return {
            "id": self.id,
            "hoja_respuesta_id": self.hoja_respuesta_id,
            "numero_pregunta": self.numero_pregunta,
            "respuesta_marcada": self.respuesta_marcada,
            "es_correcta": self.es_correcta,
            "confianza": float(self.confianza) if self.confianza else None,
            "respuesta_raw": self.respuesta_raw,
            "observacion": self.observacion,
            "requiere_revision": self.requiere_revision
        }
    
    @property
    def es_valida(self):
        """Retorna True si la respuesta es A, B, C, D o E."""
        return self.respuesta_marcada in ['A', 'B', 'C', 'D', 'E']
    
    @property
    def tipo_problema(self):
        """Retorna el tipo de problema si no es válida."""
        if self.es_valida:
            return None
        return self.respuesta_marcada  # VACIO, LETRA_INVALIDA, etc.