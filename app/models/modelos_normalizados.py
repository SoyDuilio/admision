"""
POSTULANDO - Modelos Normalizados
app/models/postulante_normalizado.py

Estructura de tablas normalizada:
1. postulantes (datos básicos)
2. postulantes_contacto
3. postulantes_academico
4. postulantes_documentos
5. postulantes_especiales
6. postulantes_asignacion
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


# ============================================================================
# TABLA PRINCIPAL - POSTULANTES (Datos Esenciales)
# ============================================================================

class Postulante(Base):
    __tablename__ = "postulantes"
    
    # Identificación
    id = Column(Integer, primary_key=True, index=True)
    codigo_postulante = Column(String(20), unique=True, index=True, nullable=False)
    
    # Datos personales básicos
    dni = Column(String(8), unique=True, index=True, nullable=False)
    nombres = Column(String(100), nullable=False)
    apellido_paterno = Column(String(100), nullable=False)
    apellido_materno = Column(String(100), nullable=False)
    fecha_nacimiento = Column(Date, nullable=False)
    sexo = Column(String(1))  # M/F
    
    # Proceso
    proceso_admision = Column(String(50), default="ADMISION_2025_2")
    
    # Estado
    estado = Column(String(50), default="registrado")
    # registrado, documentos_completos, asignado, examen_rendido, 
    # calificado, aprobado, rechazado
    
    asistio_examen = Column(Boolean, default=False)
    
    # Auditoría
    activo = Column(Boolean, default=True)
    fecha_registro = Column(DateTime, default=datetime.now)
    fecha_actualizacion = Column(DateTime, onupdate=datetime.now)
    registrado_por_usuario_id = Column(Integer)
    
    # ========================================================================
    # RELACIONES
    # ========================================================================
    contacto = relationship("PostulanteContacto", back_populates="postulante", uselist=False, cascade="all, delete-orphan")
    academico = relationship("PostulanteAcademico", back_populates="postulante", uselist=False, cascade="all, delete-orphan")
    documentos = relationship("PostulanteDocumentos", back_populates="postulante", uselist=False, cascade="all, delete-orphan")
    especiales = relationship("PostulanteEspeciales", back_populates="postulante", uselist=False, cascade="all, delete-orphan")
    asignacion = relationship("PostulanteAsignacion", back_populates="postulante", uselist=False, cascade="all, delete-orphan")
    
    verificacion_certificado = relationship("VerificacionCertificado", back_populates="postulante", uselist=False)
    venta_carpeta = relationship("VentaCarpeta", back_populates="postulante", uselist=False)
    
    hojas_respuesta = relationship("HojaRespuesta", back_populates="postulante")
    calificacion = relationship("Calificacion", back_populates="postulante", uselist=False)
    
    # ========================================================================
    # PROPIEDADES
    # ========================================================================
    
    @property
    def nombre_completo(self):
        return f"{self.apellido_paterno} {self.apellido_materno}, {self.nombres}"
    
    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = datetime.now().date()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
    
    @property
    def documentos_completos(self):
        """Verifica si todos los documentos están completos."""
        if not self.documentos or not self.venta_carpeta:
            return False
        return all([
            self.documentos.foto_archivo,
            self.documentos.dni_archivo,
            self.documentos.certificado_archivo,
            self.venta_carpeta.numero_recibo
        ])
    
    @property
    def alerta_certificado(self):
        """Indica si hay alerta con el certificado MINEDU."""
        if not self.verificacion_certificado:
            return False
        return (
            self.verificacion_certificado.consultado_minedu and 
            not self.verificacion_certificado.encontrado_en_minedu
        )
    
    @staticmethod
    def generar_codigo(proceso: str, secuencia: int) -> str:
        """Genera código único: POST-2025-2-0001"""
        proceso_limpio = proceso.replace("ADMISION_", "").replace("_", "-")
        return f"POST-{proceso_limpio}-{secuencia:04d}"


# ============================================================================
# TABLA: Contacto
# ============================================================================

class PostulanteContacto(Base):
    __tablename__ = "postulantes_contacto"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Dirección
    direccion = Column(String(255))
    distrito = Column(String(100))
    provincia = Column(String(100))
    departamento = Column(String(100))
    
    # Teléfonos
    telefono = Column(String(20))
    celular = Column(String(20))
    
    # Email
    email = Column(String(150))
    
    # Relación
    postulante = relationship("Postulante", back_populates="contacto")


# ============================================================================
# TABLA: Académico
# ============================================================================

class PostulanteAcademico(Base):
    __tablename__ = "postulantes_academico"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Programa
    programa_educativo = Column(String(200), nullable=False)
    # Ej: "Contabilidad", "Enfermería Técnica", etc.
    
    # Colegio de procedencia
    colegio_procedencia = Column(String(200))
    codigo_modular_colegio = Column(String(20))  # Código MINEDU
    anno_egreso = Column(Integer)
    
    # Relación
    postulante = relationship("Postulante", back_populates="academico")


# ============================================================================
# TABLA: Documentos
# ============================================================================

class PostulanteDocumentos(Base):
    __tablename__ = "postulantes_documentos"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Archivos
    foto_archivo = Column(String(255))
    dni_archivo = Column(String(255))
    certificado_archivo = Column(String(255))
    
    # Relación
    postulante = relationship("Postulante", back_populates="documentos")


# ============================================================================
# TABLA: Consideraciones Especiales
# ============================================================================

class PostulanteEspeciales(Base):
    __tablename__ = "postulantes_especiales"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Discapacidad
    tiene_discapacidad = Column(Boolean, default=False)
    tipo_discapacidad = Column(String(100))
    requiere_accesibilidad = Column(Boolean, default=False)
    observaciones_especiales = Column(Text)
    
    # Relación
    postulante = relationship("Postulante", back_populates="especiales")


# ============================================================================
# TABLA: Asignación
# ============================================================================

class PostulanteAsignacion(Base):
    __tablename__ = "postulantes_asignacion"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Asignación
    aula_id = Column(Integer, ForeignKey("aulas.id"))
    profesor_id = Column(Integer, ForeignKey("profesores_vigilantes.id"))
    numero_asiento = Column(Integer)
    
    fecha_asignacion = Column(DateTime)
    
    # Relación
    postulante = relationship("Postulante", back_populates="asignacion")


# ============================================================================
# TABLA: Verificación de Certificado (Ya existe, mantener)
# ============================================================================

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
    response_minedu = Column(Text)  # JSON
    
    # Decisión
    certificado_valido = Column(Boolean, default=True)
    aprobado_para_admision = Column(Boolean, default=True)
    puede_registrar_en_registra = Column(Boolean, default=True)
    observaciones = Column(Text)
    
    # Auditoría
    verificado_por_usuario_id = Column(Integer)
    fecha_verificacion = Column(DateTime, default=datetime.now)
    
    # Relación
    postulante = relationship("Postulante", back_populates="verificacion_certificado")


# ============================================================================
# TABLA: Venta de Carpeta (Ya existe, mantener)
# ============================================================================

class VentaCarpeta(Base):
    __tablename__ = "ventas_carpetas"
    
    id = Column(Integer, primary_key=True, index=True)
    postulante_id = Column(Integer, ForeignKey("postulantes.id"), unique=True, nullable=False)
    
    # Datos de la venta
    numero_recibo = Column(String(50), unique=True, nullable=False)
    monto = Column(Float, nullable=False, default=50.0)
    metodo_pago = Column(String(50))
    
    # Datos bancarios
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
    
    # Relación
    postulante = relationship("Postulante", back_populates="venta_carpeta")


# ============================================================================
# TABLA: Aula (Ya existe, mantener)
# ============================================================================

class Aula(Base):
    __tablename__ = "aulas"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo_aula = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    
    # Ubicación
    piso = Column(Integer)
    edificio = Column(String(50))
    
    # Capacidad
    capacidad_maxima = Column(Integer, nullable=False)
    capacidad_ocupada = Column(Integer, default=0)
    
    # Accesibilidad
    tiene_rampa = Column(Boolean, default=False)
    tiene_ascensor = Column(Boolean, default=False)
    piso_accesible = Column(Boolean, default=False)
    
    # Proceso
    proceso_admision = Column(String(50))
    
    # Estado
    activa = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.now)


# ============================================================================
# TABLA: Profesor Vigilante (Ya existe, mantener)
# ============================================================================

class ProfesorVigilante(Base):
    __tablename__ = "profesores_vigilantes"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo_profesor = Column(String(20), unique=True, nullable=False)
    
    # Datos personales
    dni = Column(String(8), unique=True, nullable=False)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    
    # Contacto
    celular = Column(String(20))
    email = Column(String(150))
    
    # Consideraciones
    tiene_discapacidad = Column(Boolean, default=False)
    requiere_aula_accesible = Column(Boolean, default=False)
    
    # Asignación
    aula_asignada_id = Column(Integer)
    
    # Estado
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.now)