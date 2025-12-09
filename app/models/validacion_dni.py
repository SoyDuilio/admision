"""
Modelo ValidacionDNI
Registra DNI detectados en hojas para trazabilidad
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ValidacionDNI(Base):
    __tablename__ = "validaciones_dni"
    
    id = Column(Integer, primary_key=True, index=True)
    hoja_respuesta_id = Column(Integer, ForeignKey('hojas_respuestas.id'), nullable=False, index=True)
    
    # DNI detectado (manuscrito)
    dni = Column(String(8), nullable=False, index=True)
    estado = Column(String(20), default='detectado')  # detectado, validado, discrepancia
    
    # Datos del titular (si se valida con API externa)
    nombres = Column(String(200))
    apellido_paterno = Column(String(100))
    apellido_materno = Column(String(100))
    nombres_completos = Column(String(400))
    fecha_nacimiento = Column(Date)
    sexo = Column(String(1))
    ubigeo = Column(String(6))
    direccion = Column(Text)
    
    # Metadata de validación
    api_response = Column(Text)
    fecha_captura = Column(DateTime, default=datetime.now)
    fecha_validacion = Column(DateTime)
    intentos_validacion = Column(Integer, default=0)
    ultimo_error = Column(Text)
    
    # Auditoría
    profesor_captura = Column(String(8))
    ip_captura = Column(String(50))
    
    # Relación
    hoja_respuesta = relationship("HojaRespuesta", back_populates="validacion_dni")
    
    def __repr__(self):
        return f"<ValidacionDNI(id={self.id}, dni='{self.dni}', estado='{self.estado}')>"