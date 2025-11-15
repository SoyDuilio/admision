from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime, timezone

class Profesor(Base):
    __tablename__ = "profesores"
    
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(8), unique=True, nullable=False, index=True)
    nombres = Column(String(100), nullable=False)
    apellido_paterno = Column(String(50), nullable=False)
    apellido_materno = Column(String(50))
    email = Column(String(100))
    telefono = Column(String(15))
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<Profesor {self.apellido_paterno} {self.apellido_materno}, {self.nombres}>"