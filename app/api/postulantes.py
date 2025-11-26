"""
POSTULANDO - API de Registro de Postulantes
app/api/postulantes.py

Endpoints para:
- Registrar postulante
- Lista de postulantes
- Búsqueda y filtros
- Verificación MINEDU
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, date
from pathlib import Path
import shutil
from typing import Optional, List

from app.database import get_db
from app.models import Postulante, VerificacionCertificado, VentaCarpeta

router = APIRouter()


# ============================================================================
# UTILIDADES
# ============================================================================

async def guardar_archivo(file: UploadFile, carpeta: str, prefijo: str) -> str:
    """
    Guarda un archivo y retorna el path relativo.
    """
    # Crear carpeta si no existe
    uploads_dir = Path("uploads") / carpeta
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre único
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = Path(file.filename).suffix
    filename = f"{prefijo}_{timestamp}{extension}"
    file_path = uploads_dir / filename
    
    # Guardar archivo
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return str(file_path)


def generar_codigo_postulante(proceso: str, db: Session) -> str:
    """
    Genera código único secuencial para postulante.
    Formato: POST-2025-2-0001
    """
    # Contar postulantes existentes en el proceso
    count = db.query(Postulante).filter(
        Postulante.proceso_admision == proceso
    ).count()
    
    secuencia = count + 1
    return Postulante.generar_codigo(proceso, secuencia)


def generar_numero_recibo(db: Session) -> str:
    """
    Genera número único de recibo.
    Formato: REC-2025-00001
    """
    count = db.query(VentaCarpeta).count()
    year = datetime.now().year
    return f"REC-{year}-{count + 1:05d}"


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/postulantes/registrar")
async def registrar_postulante(
    # Datos personales
    dni: str = Form(...),
    nombres: str = Form(...),
    apellido_paterno: str = Form(...),
    apellido_materno: str = Form(...),
    fecha_nacimiento: date = Form(...),
    sexo: str = Form(...),
    
    # Contacto
    celular: str = Form(...),
    telefono: Optional[str] = Form(None),
    email: str = Form(...),
    direccion: str = Form(...),
    distrito: str = Form(...),
    provincia: str = Form(...),
    departamento: str = Form(...),
    
    # Académico
    programa_educativo: str = Form(...),
    colegio_procedencia: str = Form(...),
    codigo_modular_colegio: Optional[str] = Form(None),
    anno_egreso: int = Form(...),
    
    # Documentos
    foto: UploadFile = File(...),
    dni_archivo: UploadFile = File(...),
    certificado: UploadFile = File(...),
    
    # Discapacidad
    tiene_discapacidad: bool = Form(False),
    tipo_discapacidad: Optional[str] = Form(None),
    observaciones_especiales: Optional[str] = Form(None),
    
    # Pago
    metodo_pago: str = Form(...),
    monto_carpeta: float = Form(50.0),
    numero_operacion: Optional[str] = Form(None),
    
    # Proceso
    proceso_admision: str = Form("2025-2"),
    
    db: Session = Depends(get_db)
):
    """
    Registra un nuevo postulante con todos sus datos.
    """
    
    try:
        print(f"\n{'='*70}")
        print(f"🆕 REGISTRANDO NUEVO POSTULANTE: {apellido_paterno} {apellido_materno}, {nombres}")
        print(f"{'='*70}")
        
        # ====================================================================
        # 1. VALIDACIONES
        # ====================================================================
        
        # Verificar DNI único
        existe_dni = db.query(Postulante).filter(Postulante.dni == dni).first()
        if existe_dni:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un postulante con DNI {dni}"
            )
        
        # Validar email único
        existe_email = db.query(Postulante).filter(Postulante.email == email).first()
        if existe_email:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un postulante con email {email}"
            )
        
        # ====================================================================
        # 2. GUARDAR ARCHIVOS
        # ====================================================================
        
        print("📁 Guardando archivos...")
        
        foto_path = await guardar_archivo(foto, "fotos", f"foto_{dni}")
        dni_archivo_path = await guardar_archivo(dni_archivo, "documentos", f"dni_{dni}")
        certificado_path = await guardar_archivo(certificado, "certificados", f"cert_{dni}")
        
        print(f"✓ Foto: {foto_path}")
        print(f"✓ DNI: {dni_archivo_path}")
        print(f"✓ Certificado: {certificado_path}")
        
        # ====================================================================
        # 3. GENERAR CÓDIGOS ÚNICOS
        # ====================================================================
        
        codigo_postulante = generar_codigo_postulante(proceso_admision, db)
        numero_recibo = generar_numero_recibo(db)
        
        print(f"🔖 Código generado: {codigo_postulante}")
        print(f"🧾 Recibo: {numero_recibo}")
        
        # ====================================================================
        # 4. CREAR POSTULANTE
        # ====================================================================
        
        postulante = Postulante(
            codigo_postulante=codigo_postulante,
            dni=dni,
            nombres=nombres.upper(),
            apellido_paterno=apellido_paterno.upper(),
            apellido_materno=apellido_materno.upper(),
            fecha_nacimiento=fecha_nacimiento,
            sexo=sexo,
            
            celular=celular,
            telefono=telefono,
            email=email.lower(),
            direccion=direccion,
            distrito=distrito,
            provincia=provincia,
            departamento=departamento,
            
            programa_educativo=programa_educativo,
            colegio_procedencia=colegio_procedencia,
            codigo_modular_colegio=codigo_modular_colegio,
            anno_egreso=anno_egreso,
            
            foto_archivo=foto_path,
            dni_archivo=dni_archivo_path,
            certificado_archivo=certificado_path,
            
            tiene_discapacidad=tiene_discapacidad,
            tipo_discapacidad=tipo_discapacidad if tiene_discapacidad else None,
            observaciones_especiales=observaciones_especiales if tiene_discapacidad else None,
            requiere_accesibilidad=tiene_discapacidad,
            
            carpeta_pagada=True,
            monto_carpeta=monto_carpeta,
            fecha_pago=datetime.now(),
            numero_recibo=numero_recibo,
            metodo_pago=metodo_pago,
            
            proceso_admision=proceso_admision,
            estado="registrado",
            activo=True
        )
        
        db.add(postulante)
        db.flush()  # Para obtener el ID
        
        print(f"✅ Postulante creado con ID: {postulante.id}")
        
        # ====================================================================
        # 5. REGISTRAR VENTA
        # ====================================================================
        
        venta = VentaCarpeta(
            postulante_id=postulante.id,
            numero_recibo=numero_recibo,
            monto=monto_carpeta,
            metodo_pago=metodo_pago,
            numero_operacion=numero_operacion,
            fecha_venta=datetime.now()
        )
        
        db.add(venta)
        
        print(f"💰 Venta registrada: S/ {monto_carpeta}")
        
        # ====================================================================
        # 6. VERIFICACIÓN AUTOMÁTICA DE CERTIFICADO (Asíncrono)
        # ====================================================================
        
        # TODO: Implementar verificación con API MINEDU
        # Por ahora, crear registro pendiente de verificación
        
        verificacion = VerificacionCertificado(
            postulante_id=postulante.id,
            consultado_minedu=False,
            certificado_valido=True,  # Asume válido hasta verificar
            aprobado_para_admision=True
        )
        
        db.add(verificacion)
        
        print("⏳ Verificación MINEDU programada")
        
        # ====================================================================
        # 7. COMMIT
        # ====================================================================
        
        db.commit()
        db.refresh(postulante)
        
        print(f"{'='*70}")
        print(f"✅ REGISTRO COMPLETADO")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "message": "Postulante registrado exitosamente",
            "postulante_id": postulante.id,
            "codigo_postulante": postulante.codigo_postulante,
            "numero_recibo": numero_recibo,
            "nombre_completo": postulante.nombre_completo,
            "programa": programa_educativo
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postulantes/lista")
async def listar_postulantes(
    proceso: str = "2025-2",
    programa: Optional[str] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db)
):
    """
    Lista postulantes con filtros y paginación.
    """
    
    try:
        # Query base
        query = db.query(Postulante).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.activo == True
            )
        )
        
        # Filtros
        if programa:
            query = query.filter(Postulante.programa_educativo == programa)
        
        if estado:
            query = query.filter(Postulante.estado == estado)
        
        if buscar:
            buscar_pattern = f"%{buscar}%"
            query = query.filter(
                or_(
                    Postulante.dni.like(buscar_pattern),
                    Postulante.nombres.like(buscar_pattern),
                    Postulante.apellido_paterno.like(buscar_pattern),
                    Postulante.apellido_materno.like(buscar_pattern),
                    Postulante.codigo_postulante.like(buscar_pattern)
                )
            )
        
        # Total
        total = query.count()
        
        # Paginación
        offset = (page - 1) * per_page
        postulantes = query.order_by(Postulante.fecha_registro.desc()).offset(offset).limit(per_page).all()
        
        return {
            "success": True,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "postulantes": [
                {
                    "id": p.id,
                    "codigo": p.codigo_postulante,
                    "dni": p.dni,
                    "nombre_completo": p.nombre_completo,
                    "programa": p.programa_educativo,
                    "celular": p.celular,
                    "email": p.email,
                    "estado": p.estado,
                    "carpeta_pagada": p.carpeta_pagada,
                    "documentos_completos": p.documentos_completos,
                    "alerta_certificado": p.alerta_certificado,
                    "tiene_discapacidad": p.tiene_discapacidad,
                    "fecha_registro": p.fecha_registro.isoformat()
                }
                for p in postulantes
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postulantes/{postulante_id}")
async def obtener_postulante(
    postulante_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene datos completos de un postulante.
    """
    
    postulante = db.query(Postulante).filter(Postulante.id == postulante_id).first()
    
    if not postulante:
        raise HTTPException(status_code=404, detail="Postulante no encontrado")
    
    return {
        "success": True,
        "postulante": {
            "id": postulante.id,
            "codigo": postulante.codigo_postulante,
            "dni": postulante.dni,
            "nombres": postulante.nombres,
            "apellido_paterno": postulante.apellido_paterno,
            "apellido_materno": postulante.apellido_materno,
            "nombre_completo": postulante.nombre_completo,
            "fecha_nacimiento": postulante.fecha_nacimiento.isoformat(),
            "edad": postulante.edad,
            "sexo": postulante.sexo,
            
            "celular": postulante.celular,
            "telefono": postulante.telefono,
            "email": postulante.email,
            "direccion": postulante.direccion,
            "distrito": postulante.distrito,
            "provincia": postulante.provincia,
            "departamento": postulante.departamento,
            
            "programa_educativo": postulante.programa_educativo,
            "colegio_procedencia": postulante.colegio_procedencia,
            "codigo_modular_colegio": postulante.codigo_modular_colegio,
            "anno_egreso": postulante.anno_egreso,
            
            "tiene_discapacidad": postulante.tiene_discapacidad,
            "tipo_discapacidad": postulante.tipo_discapacidad,
            "observaciones_especiales": postulante.observaciones_especiales,
            
            "carpeta_pagada": postulante.carpeta_pagada,
            "monto_carpeta": postulante.monto_carpeta,
            "numero_recibo": postulante.numero_recibo,
            "metodo_pago": postulante.metodo_pago,
            
            "estado": postulante.estado,
            "documentos_completos": postulante.documentos_completos,
            "alerta_certificado": postulante.alerta_certificado,
            
            "fecha_registro": postulante.fecha_registro.isoformat()
        }
    }


@router.get("/postulantes/sin-certificado")
async def postulantes_sin_certificado_minedu(
    proceso: str = "2025-2",
    db: Session = Depends(get_db)
):
    """
    Lista postulantes cuyo certificado NO está en MINEDU.
    CRÍTICO para trazabilidad.
    """
    
    postulantes = db.query(Postulante).filter(
        and_(
            Postulante.proceso_admision == proceso,
            Postulante.certificado_minedu_verificado == True,
            Postulante.certificado_minedu_existe == False,
            Postulante.activo == True
        )
    ).all()
    
    return {
        "success": True,
        "total": len(postulantes),
        "postulantes": [
            {
                "id": p.id,
                "codigo": p.codigo_postulante,
                "dni": p.dni,
                "nombre_completo": p.nombre_completo,
                "programa": p.programa_educativo,
                "colegio": p.colegio_procedencia,
                "anno_egreso": p.anno_egreso,
                "observaciones": p.certificado_observaciones,
                "fecha_verificacion": p.fecha_verificacion_certificado.isoformat() if p.fecha_verificacion_certificado else None
            }
            for p in postulantes
        ]
    }


@router.get("/postulantes/estadisticas")
async def estadisticas_postulantes(
    proceso: str = "2025-2",
    db: Session = Depends(get_db)
):
    """
    Estadísticas generales de postulantes.
    """
    
    try:
        # Total
        total = db.query(Postulante).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.activo == True
            )
        ).count()
        
        # Por programa
        por_programa = db.query(
            Postulante.programa_educativo,
            func.count(Postulante.id).label('total')
        ).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.activo == True
            )
        ).group_by(Postulante.programa_educativo).all()
        
        # Por estado
        por_estado = db.query(
            Postulante.estado,
            func.count(Postulante.id).label('total')
        ).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.activo == True
            )
        ).group_by(Postulante.estado).all()
        
        # Con discapacidad
        con_discapacidad = db.query(Postulante).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.tiene_discapacidad == True,
                Postulante.activo == True
            )
        ).count()
        
        # Sin certificado MINEDU
        sin_certificado_minedu = db.query(Postulante).filter(
            and_(
                Postulante.proceso_admision == proceso,
                Postulante.certificado_minedu_verificado == True,
                Postulante.certificado_minedu_existe == False,
                Postulante.activo == True
            )
        ).count()
        
        return {
            "success": True,
            "total_postulantes": total,
            "por_programa": [{"programa": p[0], "total": p[1]} for p in por_programa],
            "por_estado": [{"estado": e[0], "total": e[1]} for e in por_estado],
            "con_discapacidad": con_discapacidad,
            "sin_certificado_minedu": sin_certificado_minedu
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))