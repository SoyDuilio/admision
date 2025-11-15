"""
POSTULANDO - API de Generación de Hojas
app/api/generacion.py

Endpoints para generar hojas de respuestas y obtener datos necesarios.

CAMBIO CRÍTICO:
- Ahora REGISTRA en BD antes de generar PDFs
- Guarda codigo_hoja en hojas_respuestas
"""

from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from io import BytesIO
import zipfile
import tempfile
import os
from datetime import datetime

from app.database import get_db
from app.models import Postulante, HojaRespuesta, Profesor, Aula
from app.services.pdf_generator_v2 import generar_hoja_respuestas_v2
from app.utils import generar_codigo_hoja_unico

router = APIRouter()

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def crear_directorio_generadas():
    """Crea directorio para hojas generadas si no existe"""
    import os
    os.makedirs("uploads/hojas_generadas", exist_ok=True)

# ============================================================================
# ENDPOINTS DE GENERACIÓN
# ============================================================================

@router.post("/generar-hojas")
async def generar_hojas(
    tipo: str = Form(...),
    postulante_id: Optional[int] = Form(None),
    rango_inicio: Optional[int] = Form(None),
    rango_fin: Optional[int] = Form(None),
    cantidad_hojas: Optional[int] = Form(100),
    incluir_datos: bool = Form(True),
    incluir_firma: bool = Form(True),
    proceso_admision: str = Form("2025-2"),
    codigo_aula: Optional[str] = Form(None),
    dni_profesor: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Genera hojas de respuestas y las registra en BD.
    
    CORREGIDO:
    - Registra en hojas_respuestas ANTES de generar PDF
    - Guarda codigo_hoja único
    - Si no se envía aula/profesor, usa el primero disponible
    """
    
    try:
        # ====================================================================
        # 1. OBTENER AULA Y PROFESOR (si no vienen del frontend)
        # ====================================================================
        
        if not codigo_aula:
            primera_aula = db.query(Aula).first()
            if primera_aula:
                codigo_aula = primera_aula.codigo
                print(f"📍 Usando aula por defecto: {codigo_aula}")
            else:
                raise HTTPException(status_code=400, detail="No hay aulas registradas en BD")
        
        if not dni_profesor:
            primer_profesor = db.query(Profesor).first()
            if primer_profesor:
                dni_profesor = primer_profesor.dni
                print(f"👨‍🏫 Usando profesor por defecto: {dni_profesor} ({primer_profesor.nombres})")
            else:
                raise HTTPException(status_code=400, detail="No hay profesores registrados en BD")
        
        # Verificar que existan en BD
        aula = db.query(Aula).filter_by(codigo=codigo_aula).first()
        if not aula:
            raise HTTPException(status_code=404, detail=f"Aula {codigo_aula} no existe")
        
        profesor = db.query(Profesor).filter_by(dni=dni_profesor).first()
        if not profesor:
            raise HTTPException(status_code=404, detail=f"Profesor {dni_profesor} no existe")
        
        print(f"✅ Aula validada: {codigo_aula} - {aula.nombre}")
        print(f"✅ Profesor validado: {dni_profesor} - {profesor.nombres}")
        
        # ====================================================================
        # 2. OBTENER POSTULANTES
        # ====================================================================
        
        postulantes_data = []
        
        if tipo == "todos":
            postulantes = db.query(Postulante).all()
            print(f"📋 Obtenidos {len(postulantes)} postulantes (todos)")
            
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,
                    "postulante_id": p.id,
                    "datos": {
                        "dni": p.dni,
                        "nombres": p.nombres,
                        "apellido_paterno": p.apellido_paterno,
                        "apellido_materno": p.apellido_materno,
                        "programa": p.programa_educativo
                    } if incluir_datos else None
                })
                
        elif tipo == "individual":
            postulante = db.query(Postulante).filter_by(id=postulante_id).first()
            if not postulante:
                raise HTTPException(status_code=404, detail="Postulante no encontrado")
            
            print(f"📋 Postulante individual: {postulante.dni}")
            
            postulantes_data.append({
                "codigo": postulante.dni,
                "postulante_id": postulante.id,
                "datos": {
                    "dni": postulante.dni,
                    "nombres": postulante.nombres,
                    "apellido_paterno": postulante.apellido_paterno,
                    "apellido_materno": postulante.apellido_materno,
                    "programa": postulante.programa_educativo
                } if incluir_datos else None
            })
            
        elif tipo == "rango":
            postulantes = db.query(Postulante).slice(rango_inicio - 1, rango_fin).all()
            print(f"📋 Obtenidos {len(postulantes)} postulantes (rango {rango_inicio}-{rango_fin})")
            
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,
                    "postulante_id": p.id,
                    "datos": {
                        "dni": p.dni,
                        "nombres": p.nombres,
                        "apellido_paterno": p.apellido_paterno,
                        "apellido_materno": p.apellido_materno,
                        "programa": p.programa_educativo
                    } if incluir_datos else None
                })
                
        elif tipo == "sin_identificar":
            print(f"📋 Generando {cantidad_hojas} hojas sin identificar")
            for i in range(cantidad_hojas):
                postulantes_data.append({
                    "codigo": f"SIN-ID-{i+1:04d}",
                    "postulante_id": None,
                    "datos": None
                })
        
        if not postulantes_data:
            raise HTTPException(status_code=400, detail="No hay postulantes para generar hojas")
        
        # ====================================================================
        # 3. GENERAR PDFs Y REGISTRAR EN BD
        # ====================================================================
        
        temp_dir = tempfile.mkdtemp()
        pdf_files = []
        hojas_registradas = []
        hojas_sin_registrar = []
        
        crear_directorio_generadas()
        
        for idx, item in enumerate(postulantes_data, 1):
            print(f"\n{'='*60}")
            print(f"📄 Procesando hoja {idx}/{len(postulantes_data)}")
            print(f"   DNI: {item['codigo']}")
            print(f"   Postulante ID: {item['postulante_id']}")
            
            # Generar código único
            codigo_hoja = generar_codigo_hoja_unico()
            
            # Verificar que sea único
            intentos = 0
            while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                codigo_hoja = generar_codigo_hoja_unico()
                intentos += 1
                if intentos > 10:
                    raise Exception("No se pudo generar código único después de 10 intentos")
            
            print(f"   Código generado: {codigo_hoja}")
            
            # ====================================================================
            # CRÍTICO: REGISTRAR EN BD ANTES DE GENERAR PDF
            # ====================================================================
            
            if item['postulante_id']:
                try:
                    # Verificar si ya existe hoja para este postulante
                    hoja_existente = db.query(HojaRespuesta).filter_by(
                        postulante_id=item['postulante_id'],
                        proceso_admision=proceso_admision
                    ).first()
                    
                    if hoja_existente:
                        # REIMPRESIÓN: actualizar código
                        print(f"   🔄 REIMPRESIÓN - Actualizando código")
                        hoja_existente.codigo_hoja = codigo_hoja
                        hoja_existente.dni_profesor = dni_profesor
                        hoja_existente.codigo_aula = codigo_aula
                        hoja_existente.updated_at = datetime.now()
                        hoja = hoja_existente
                    else:
                        # PRIMERA VEZ: crear registro nuevo
                        print(f"   ✨ PRIMERA VEZ - Creando registro")
                        hoja = HojaRespuesta(
                            postulante_id=item['postulante_id'],
                            dni_profesor=dni_profesor,
                            codigo_aula=codigo_aula,
                            codigo_hoja=codigo_hoja,
                            proceso_admision=proceso_admision,
                            estado="generada"
                        )
                        db.add(hoja)
                    
                    db.flush()  # Para obtener el ID
                    
                    hojas_registradas.append({
                        "codigo_hoja": codigo_hoja,
                        "dni": item['codigo'],
                        "hoja_id": hoja.id
                    })
                    print(f"   ✅ Registrado en BD (ID: {hoja.id})")
                    
                except Exception as e:
                    print(f"   ⚠️ Error al registrar en BD: {str(e)}")
                    hojas_sin_registrar.append({
                        "codigo_hoja": codigo_hoja,
                        "dni": item['codigo'],
                        "error": str(e)
                    })
            else:
                print(f"   ⏭️ Sin postulante_id, no se registra en BD")
                hojas_sin_registrar.append({
                    "codigo_hoja": codigo_hoja,
                    "dni": item['codigo'],
                    "razon": "sin_identificar"
                })
            
            # GENERAR PDF
            filename = f"hoja_{item['codigo']}_{codigo_hoja}.pdf"
            filepath = os.path.join(temp_dir, filename)
            
            try:
                generar_hoja_respuestas_v2(
                    output_path=filepath,
                    dni_postulante=item['codigo'],
                    codigo_aula=codigo_aula,
                    dni_profesor=dni_profesor,
                    codigo_hoja=codigo_hoja,
                    proceso=proceso_admision
                )
                pdf_files.append(filepath)
                print(f"   ✅ PDF generado: {filename}")
                
            except Exception as e:
                print(f"   ❌ Error al generar PDF: {str(e)}")
                raise
        
        # ====================================================================
        # 4. COMMIT A BD
        # ====================================================================
        
        try:
            db.commit()
            print(f"\n{'='*60}")
            print(f"✅ COMMIT EXITOSO")
            print(f"   Hojas registradas en BD: {len(hojas_registradas)}")
            print(f"   Hojas sin registrar: {len(hojas_sin_registrar)}")
            
        except Exception as e:
            db.rollback()
            print(f"\n❌ ERROR EN COMMIT: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al guardar en BD: {str(e)}")
        
        # ====================================================================
        # 5. CREAR ZIP
        # ====================================================================
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for pdf_file in pdf_files:
                zip_file.write(pdf_file, os.path.basename(pdf_file))
        
        zip_buffer.seek(0)
        
        # Limpiar temporales
        for pdf_file in pdf_files:
            os.remove(pdf_file)
        os.rmdir(temp_dir)
        
        # ====================================================================
        # 6. RESPUESTA
        # ====================================================================
        
        filename = f"hojas_respuestas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        print(f"\n✅ Proceso completado")
        print(f"   Archivo ZIP: {filename}")
        print(f"   Total PDFs: {len(pdf_files)}")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Total-Hojas": str(len(pdf_files)),
                "X-Hojas-Registradas": str(len(hojas_registradas)),
                "X-Hojas-Sin-Registrar": str(len(hojas_sin_registrar))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profesores")
async def obtener_profesores(db: Session = Depends(get_db)):
    """Obtiene lista de profesores para selección"""
    profesores = db.query(Profesor).all()
    
    return {
        "success": True,
        "total": len(profesores),
        "profesores": [
            {
                "id": p.id,
                "dni": p.dni,
                "nombres": p.nombres,
                "apellido_paterno": p.apellido_paterno,
                "apellido_materno": p.apellido_materno,
                "nombre_completo": f"{p.apellido_paterno} {p.apellido_materno}, {p.nombres}"
            }
            for p in profesores
        ]
    }


@router.get("/aulas")
async def obtener_aulas(db: Session = Depends(get_db)):
    """Obtiene lista de aulas para selección"""
    aulas = db.query(Aula).all()
    
    return {
        "success": True,
        "total": len(aulas),
        "aulas": [
            {
                "id": a.id,
                "codigo": a.codigo,
                "nombre": a.nombre,
                "capacidad": a.capacidad
            }
            for a in aulas
        ]
    }


@router.get("/progreso-generacion/{proceso}")
async def obtener_progreso_generacion(
    proceso: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el progreso de generación de hojas.
    Útil para mostrar en frontend cuántas faltan.
    """
    
    from app.models import AsignacionExamen
    
    # Total de asignaciones
    total_asignaciones = db.query(AsignacionExamen).filter(
        AsignacionExamen.proceso_admision == proceso
    ).count()
    
    # Asignaciones confirmadas (con hoja generada)
    confirmadas = db.query(AsignacionExamen).filter(
        AsignacionExamen.proceso_admision == proceso,
        AsignacionExamen.estado == 'confirmado'
    ).count()
    
    # Asignaciones pendientes
    pendientes = db.query(AsignacionExamen).filter(
        AsignacionExamen.proceso_admision == proceso,
        AsignacionExamen.estado == 'asignado'
    ).count()
    
    # Hojas en BD
    hojas_generadas = db.query(HojaRespuesta).filter(
        HojaRespuesta.proceso_admision == proceso
    ).count()
    
    porcentaje = (confirmadas / total_asignaciones * 100) if total_asignaciones > 0 else 0
    
    return {
        "success": True,
        "proceso": proceso,
        "total_asignaciones": total_asignaciones,
        "confirmadas": confirmadas,
        "pendientes": pendientes,
        "hojas_generadas": hojas_generadas,
        "porcentaje_completado": round(porcentaje, 1)
    }


@router.post("/verificar-datos-generacion")
async def verificar_datos_generacion(db: Session = Depends(get_db)):
    """
    Verifica que existan datos necesarios para generar hojas.
    Útil para mostrar warnings en frontend.
    """
    total_postulantes = db.query(Postulante).count()
    total_profesores = db.query(Profesor).count()
    total_aulas = db.query(Aula).count()
    
    errores = []
    warnings = []
    
    if total_postulantes == 0:
        errores.append("No hay postulantes registrados")
    
    if total_profesores == 0:
        errores.append("No hay profesores registrados")
    
    if total_aulas == 0:
        errores.append("No hay aulas registradas")
    
    if total_postulantes < 10:
        warnings.append(f"Solo hay {total_postulantes} postulante(s) registrado(s)")
    
    puede_generar = len(errores) == 0
    
    return {
        "success": True,
        "puede_generar": puede_generar,
        "errores": errores,
        "warnings": warnings,
        "estadisticas": {
            "postulantes": total_postulantes,
            "profesores": total_profesores,
            "aulas": total_aulas
        }
    }


@router.post("/generar-hojas-desde-asignaciones")
async def generar_hojas_desde_asignaciones(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Genera hojas de respuestas usando las asignaciones guardadas en BD.
    
    FLUJO:
    1. Lee asignaciones_examen del proceso
    2. FILTRA las que NO tienen hoja generada
    3. Por cada asignación, genera PDF con aula/profesor correcto
    4. Crea registro en hojas_respuestas
    5. Marca asignación como 'confirmado'
    6. Retorna ZIP con todos los PDFs
    
    Body:
    {
        "proceso_admision": "2025-2",
        "solo_pendientes": true
    }
    """
    
    from app.models import AsignacionExamen
    
    proceso = data.get('proceso_admision', '2025-2')
    solo_pendientes = data.get('solo_pendientes', True)
    
    print(f"\n{'='*70}")
    print(f"📄 GENERANDO HOJAS DESDE ASIGNACIONES")
    print(f"{'='*70}")
    print(f"Proceso: {proceso}")
    print(f"Solo pendientes: {solo_pendientes}")
    
    # ====================================================================
    # 1. OBTENER ASIGNACIONES SIN HOJA GENERADA
    # ====================================================================
    
    if solo_pendientes:
        # Obtener IDs de postulantes que YA tienen hoja generada
        postulantes_con_hoja = db.query(HojaRespuesta.postulante_id).filter(
            HojaRespuesta.proceso_admision == proceso,
            HojaRespuesta.estado.in_(['generada', 'procesado', 'calificado'])
        ).distinct().all()
        
        ids_con_hoja = [p[0] for p in postulantes_con_hoja]
        
        print(f"   ℹ️  Postulantes con hoja: {len(ids_con_hoja)}")
        
        # Filtrar asignaciones
        if ids_con_hoja:
            asignaciones = db.query(AsignacionExamen).filter(
                AsignacionExamen.proceso_admision == proceso,
                ~AsignacionExamen.postulante_id.in_(ids_con_hoja)
            ).all()
        else:
            asignaciones = db.query(AsignacionExamen).filter(
                AsignacionExamen.proceso_admision == proceso
            ).all()
    else:
        # Todas las asignaciones (regenerar todo)
        asignaciones = db.query(AsignacionExamen).filter(
            AsignacionExamen.proceso_admision == proceso
        ).all()
    
    if not asignaciones:
        return {
            "success": True,
            "message": "No hay asignaciones pendientes de generar",
            "total_generadas": 0
        }
    
    print(f"✅ Encontradas {len(asignaciones)} asignaciones PENDIENTES")
    
    # ====================================================================
    # 2. GENERAR PDFs
    # ====================================================================
    
    temp_dir = tempfile.mkdtemp()
    pdf_files = []
    hojas_generadas = []
    errores = []
    
    crear_directorio_generadas()
    
    for idx, asignacion in enumerate(asignaciones, 1):
        try:
            # Imprimir progreso cada 10 hojas
            if idx % 10 == 0 or idx == 1:
                print(f"\n📊 Progreso: {idx}/{len(asignaciones)}")
            
            # Obtener datos relacionados
            postulante = asignacion.postulante
            aula = asignacion.aula
            
            if not postulante or not aula:
                errores.append({
                    "asignacion_id": asignacion.id,
                    "error": "Datos incompletos"
                })
                continue
            
            # Obtener profesor
            profesor = db.query(Profesor).filter(Profesor.activo == True).first()
            
            if not profesor:
                errores.append({
                    "asignacion_id": asignacion.id,
                    "error": "No hay profesores activos"
                })
                continue
            
            # Generar código único
            codigo_hoja = generar_codigo_hoja_unico()
            
            intentos = 0
            while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                codigo_hoja = generar_codigo_hoja_unico()
                intentos += 1
                if intentos > 10:
                    raise Exception("No se pudo generar código único")
            
            # ================================================================
            # CREAR REGISTRO EN BD (NO actualizar, siempre crear nuevo)
            # ================================================================
            
            hoja = HojaRespuesta(
                postulante_id=postulante.id,
                dni_profesor=profesor.dni,
                codigo_aula=aula.codigo,
                codigo_hoja=codigo_hoja,
                proceso_admision=proceso,
                estado="generada"
            )
            db.add(hoja)
            
            # ================================================================
            # GENERAR PDF
            # ================================================================
            
            filename = f"hoja_{postulante.dni}_{codigo_hoja}.pdf"
            filepath = os.path.join(temp_dir, filename)
            
            generar_hoja_respuestas_v2(
                output_path=filepath,
                dni_postulante=postulante.dni,
                codigo_aula=aula.codigo,
                dni_profesor=profesor.dni,
                codigo_hoja=codigo_hoja,
                proceso=proceso
            )
            
            pdf_files.append(filepath)
            
            # ================================================================
            # MARCAR ASIGNACIÓN COMO CONFIRMADA
            # ================================================================
            
            asignacion.estado = 'confirmado'
            
            hojas_generadas.append({
                "postulante_dni": postulante.dni,
                "postulante_nombre": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "codigo_hoja": codigo_hoja,
                "aula": aula.codigo,
                "hoja_id": hoja.id
            })
            
            # ================================================================
            # COMMIT PARCIAL CADA 10 HOJAS (para progreso visible)
            # ================================================================
            
            if idx % 10 == 0:
                try:
                    db.commit()
                    print(f"   💾 Commit parcial: {idx} hojas guardadas")
                except Exception as e:
                    print(f"   ⚠️  Error en commit parcial: {str(e)}")
                    db.rollback()
                    # Continuar con las siguientes
            
        except Exception as e:
            print(f"   ❌ ERROR en {postulante.dni if postulante else 'unknown'}: {str(e)}")
            errores.append({
                "asignacion_id": asignacion.id,
                "error": str(e)
            })
    
    # ====================================================================
    # 3. COMMIT A BD
    # ====================================================================
    
    try:
        db.commit()
        print(f"\n{'='*60}")
        print(f"✅ COMMIT EXITOSO")
        print(f"   Hojas generadas: {len(hojas_generadas)}")
        print(f"   Errores: {len(errores)}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR EN COMMIT: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")
    
    # ====================================================================
    # 4. CREAR ZIP
    # ====================================================================
    
    if not pdf_files:
        return {
            "success": False,
            "message": "No se generaron PDFs",
            "errores": errores
        }
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for pdf_file in pdf_files:
            zip_file.write(pdf_file, os.path.basename(pdf_file))
    
    zip_buffer.seek(0)
    
    # Limpiar temporales
    for pdf_file in pdf_files:
        try:
            os.remove(pdf_file)
        except:
            pass
    
    try:
        os.rmdir(temp_dir)
    except:
        pass
    
    # ====================================================================
    # 5. RESPUESTA
    # ====================================================================
    
    filename = f"hojas_asignadas_{proceso}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    print(f"\n✅ Proceso completado")
    print(f"   Archivo ZIP: {filename}")
    print(f"   Total PDFs: {len(pdf_files)}\n")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Total-Hojas": str(len(pdf_files)),
            "X-Hojas-Generadas": str(len(hojas_generadas)),
            "X-Errores": str(len(errores))
        }
    )