"""
Modelo: Venta de Carpeta de Postulante
app/models/venta_carpeta.py
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class VentaCarpeta(Base):
    __tablename__ = "ventas_carpetas"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Datos de la venta
    numero_recibo = Column(String(50), unique=True, nullable=False)
    monto = Column(Float, nullable=False, default=50.0)
    metodo_pago = Column(String(50))  # Efectivo, Transferencia, etc.
    
    # Datos bancarios (si aplica)
    numero_operacion = Column(String(100))
    banco = Column(String(100))
    
    # Comprobante
    comprobante_archivo = Column(String(255))
    
    # Auditoría
    fecha_venta = Column(DateTime, default=datetime.now)
    vendedor_usuario_id = Column(Integer)
    
    # Estado
    anulado = Column(Boolean, default=False)
    fecha_anulacion = Column(DateTime)
    motivo_anulacion = Column(Text)
    
    # Relación (opcional)
    # postulante = relationship("Postulante", back_populates="venta_carpeta")