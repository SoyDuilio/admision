"""
Schemas de Pydantic para Postulante
Validación de datos de entrada/salida
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime


class PostulanteBase(BaseModel):
    """Schema base de Postulante"""
    dni: str = Field(..., min_length=8, max_length=8, description="DNI del postulante")
    nombre: str = Field(..., min_length=2, max_length=200)
    apellido_paterno: str = Field(..., min_length=2, max_length=100)
    apellido_materno: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=15)
    programa_estudio: Optional[str] = Field(None, max_length=200)
    
    @validator('dni')
    def validate_dni(cls, v):
        """Valida que el DNI solo contenga números"""
        if not v.isdigit():
            raise ValueError('DNI debe contener solo números')
        return v
    
    @validator('telefono')
    def validate_telefono(cls, v):
        """Valida formato de teléfono"""
        if v and not v.replace('+', '').replace(' ', '').isdigit():
            raise ValueError('Teléfono debe contener solo números')
        return v


class PostulanteCreate(PostulanteBase):
    """Schema para crear un postulante"""
    pass


class PostulanteUpdate(BaseModel):
    """Schema para actualizar un postulante"""
    nombre: Optional[str] = Field(None, min_length=2, max_length=200)
    apellido_paterno: Optional[str] = Field(None, min_length=2, max_length=100)
    apellido_materno: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=15)
    programa_estudio: Optional[str] = Field(None, max_length=200)
    activo: Optional[bool] = None


class PostulanteResponse(PostulanteBase):
    """Schema de respuesta de Postulante"""
    id: int
    codigo: str
    activo: bool
    examen_rendido: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Antes era orm_mode en Pydantic v1


class PostulanteListItem(BaseModel):
    """Schema simplificado para listas de postulantes"""
    id: int
    dni: str
    nombre_completo: str
    codigo: str
    examen_rendido: bool
    activo: bool
    
    class Config:
        from_attributes = True


class PostulanteSelector(BaseModel):
    """Schema para selector de postulantes (dropdown)"""
    id: int
    dni: str
    nombre_completo: str
    codigo: str
    
    class Config:
        from_attributes = True