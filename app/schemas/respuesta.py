"""
Schemas de Pydantic para Respuestas
Validación de datos de respuestas individuales y procesamiento
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime

from app.schemas.postulante import PostulanteListItem

class RespuestaBase(BaseModel):
    """Schema base de Respuesta"""
    numero_pregunta: int = Field(..., ge=1, le=100, description="Número de pregunta (1-100)")
    respuesta: Optional[str] = Field(None, max_length=1, description="Respuesta: A, B, C, D, E, o null")
    confianza: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confianza del reconocimiento (0-1)")
    
    @validator('respuesta')
    def validate_respuesta(cls, v):
        """Valida que la respuesta sea una letra válida"""
        if v is not None and v not in ['A', 'B', 'C', 'D', 'E', '?']:
            raise ValueError('Respuesta debe ser A, B, C, D, E, ? o null')
        return v


class RespuestaCreate(RespuestaBase):
    """Schema para crear una respuesta"""
    hoja_respuesta_id: int


class RespuestaResponse(RespuestaBase):
    """Schema de respuesta de Respuesta"""
    id: int
    hoja_respuesta_id: int
    es_correcta: Optional[bool]
    marcada_revision: bool
    
    class Config:
        from_attributes = True


# Schemas para procesamiento de imágenes

class VisionAPIRequest(BaseModel):
    """Request para procesar imagen con Vision API"""
    postulante_id: int
    imagen_base64: Optional[str] = None  # Imagen en base64
    tipo: str = Field(..., description="'estudiante' o 'clave'")
    
    @validator('tipo')
    def validate_tipo(cls, v):
        if v not in ['estudiante', 'clave']:
            raise ValueError("Tipo debe ser 'estudiante' o 'clave'")
        return v


class RespuestaDetectada(BaseModel):
    """Una respuesta detectada por la Vision API"""
    numero_pregunta: int = Field(..., ge=1, le=100)
    respuesta: Optional[str] = Field(None, max_length=1)
    confianza: float = Field(default=1.0, ge=0.0, le=1.0)


class VisionAPIResponse(BaseModel):
    """Respuesta del procesamiento con Vision API"""
    success: bool
    api_usada: str  # "google", "openai", "claude"
    tiempo_procesamiento: float  # segundos
    respuestas: List[RespuestaDetectada]
    total_detectadas: int
    confianza_promedio: float
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None


class HojaRespuestaCreate(BaseModel):
    """Schema para crear metadata de hoja de respuesta"""
    postulante_id: int
    imagen_path: str
    imagen_size_kb: Optional[int] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None


class HojaRespuestaResponse(BaseModel):
    """Schema de respuesta de HojaRespuesta"""
    id: int
    postulante_id: int
    imagen_path: str
    procesada: bool
    api_usada: Optional[str]
    tiempo_procesamiento: Optional[float]
    respuestas_detectadas: int
    confianza_promedio: Optional[float]
    gps_valido: bool
    created_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ClaveRespuestaCreate(BaseModel):
    """Schema para crear clave de respuesta"""
    numero_pregunta: int = Field(..., ge=1, le=100)
    respuesta_correcta: str = Field(..., max_length=1)
    tema: Optional[str] = None
    
    @validator('respuesta_correcta')
    def validate_respuesta_correcta(cls, v):
        if v not in ['A', 'B', 'C', 'D', 'E']:
            raise ValueError('Respuesta correcta debe ser A, B, C, D o E')
        return v


class ClaveRespuestaResponse(BaseModel):
    """Schema de respuesta de ClaveRespuesta"""
    id: int
    numero_pregunta: int
    respuesta_correcta: str
    tema: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CalificacionCreate(BaseModel):
    """Schema para crear calificación"""
    postulante_id: int
    nota: int = Field(..., ge=0, le=100)
    correctas: int = Field(..., ge=0, le=100)
    incorrectas: int = Field(..., ge=0, le=100)
    en_blanco: int = Field(..., ge=0, le=100)
    no_legibles: int = Field(default=0, ge=0, le=100)
    aprobado: bool
    nota_minima: int = Field(default=70, ge=0, le=100)


class CalificacionResponse(BaseModel):
    """Schema de respuesta de Calificación"""
    id: int
    postulante_id: int
    nota: int
    correctas: int
    incorrectas: int
    en_blanco: int
    no_legibles: int
    porcentaje_aciertos: Optional[float]
    aprobado: bool
    nota_minima: int
    puesto: Optional[int]
    created_at: datetime
    calificado_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ResultadoCompleto(BaseModel):
    """Schema completo de resultado con datos del postulante"""
    postulante: PostulanteListItem
    calificacion: CalificacionResponse
    
    class Config:
        from_attributes = True


# Schema para la demo

class EstadisticasDemo(BaseModel):
    """Estadísticas generales de la demo"""
    total_postulantes: int
    examenes_procesados: int
    examenes_pendientes: int
    promedio_nota: Optional[float]
    aprobados: int
    desaprobados: int
    clave_cargada: bool