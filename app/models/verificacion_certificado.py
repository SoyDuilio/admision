"""
Modelo: Verificación de Certificado MINEDU
app/models/verificacion_certificado.py
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class VerificacionCertificado(Base):
    __tablename__ = "verificaciones_certificado"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Datos del certificado
    numero_certificado = Column(String(100))
    anno_emision = Column(Integer)
    colegio_emisor = Column(String(200))
    codigo_modular = Column(String(20))
    
    # Verificación MINEDU
    consultado_minedu = Column(Boolean, default=False)
    fecha_consulta = Column(DateTime)
    encontrado_en_minedu = Column(Boolean, nullable=True)
    
    # Respuesta API
    response_minedu = Column(Text)  # JSON stringificado
    
    # Decisión
    certificado_valido = Column(Boolean, default=True)
    aprobado_para_admision = Column(Boolean, default=True)
    puede_registrar_en_registra = Column(Boolean, default=True)
    observaciones = Column(Text)
    
    # Auditoría
    verificado_por_usuario_id = Column(Integer)
    fecha_verificacion = Column(DateTime, default=datetime.now)
    
    # Relación (opcional)
    # postulante = relationship("Postulante", back_populates="verificacion_certificado")