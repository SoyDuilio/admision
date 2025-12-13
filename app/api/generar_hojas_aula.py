"""
API para Generación de Hojas por Aula
app/api/generar_hojas_aula.py

ACTUALIZADO para usar la estructura real de Railway
"""


from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Aula, Postulante, Profesor
from app.models.hoja_respuesta import HojaRespuesta

from app.services.asignacion_alfabetica import asignar_alfabeticamente

router = APIRouter()

@router.get("/verificar-asignaciones-completas")
async def verificar_asignaciones_completas(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Verifica si todas las asignaciones están completas.
    Usa la tabla asignaciones_examen (no postulantes_asignacion)
    
    CORREGIDO: Retorna correctamente total_aulas y total_profesores
    """
    
    try:
        # Total de postulantes del proceso
        total_postulantes = db.query(func.count(Postulante.id)).filter(
            Postulante.activo == True,
            Postulante.proceso_admision == proceso
        ).scalar() or 0
        
        # Total de aulas activas
        total_aulas = db.query(func.count(Aula.id)).filter(
            Aula.activo == True
        ).scalar() or 0
        
        # Total de profesores activos
        total_profesores = db.query(func.count(Profesor.id)).filter(
            Profesor.activo == True
        ).scalar() or 0
        
        # Total asignados en asignaciones_examen
        query_asignados = text("""
            SELECT COUNT(DISTINCT ae.postulante_id) 
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.activo = true 
              AND p.proceso_admision = :proceso
        """)
        result = db.execute(query_asignados, {"proceso": proceso})
        total_asignados = result.scalar() or 0
        
        # Capacidad total de aulas
        query_capacidad = text("""
            SELECT COALESCE(SUM(capacidad), 0)
            FROM aulas
            WHERE activo = true
        """)
        capacidad_total = db.execute(query_capacidad).scalar() or 0
        
        # Verificar si hay suficiente capacidad
        capacidad_suficiente = capacidad_total >= total_postulantes
        
        # Asignaciones del proceso actual
        query_asignaciones_proceso = text("""
            SELECT COUNT(*) 
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.activo = true 
              AND p.proceso_admision = :proceso
        """)
        total_asignaciones = db.execute(query_asignaciones_proceso, {"proceso": proceso}).scalar() or 0
        
        return {
            "success": True,
            "proceso": proceso,
            "total_postulantes": total_postulantes,
            "total_aulas": total_aulas,
            "total_profesores": total_profesores,
            "total_asignados": total_asignados,
            "total_asignaciones": total_asignaciones,
            "capacidad_total": capacidad_total,
            "capacidad_suficiente": capacidad_suficiente,
            "asignaciones_completas": total_asignados == total_postulantes,
            "puede_generar": (
                total_postulantes > 0 and 
                total_aulas > 0 and 
                total_profesores > 0 and
                capacidad_suficiente
            )
        }
        
    except Exception as e:
        print(f"❌ Error en verificar_asignaciones_completas: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/aulas-con-asignaciones")
async def listar_aulas_con_asignaciones(
    proceso: str = Query("2025-2"),
    formato: str = Query("simple", description="simple o detallado"),
    db: Session = Depends(get_db)
):
    """
    Lista aulas con postulantes asignados.
    
    Parámetros:
    - formato="simple": retorna lista plana [id, codigo, nombre, total]
    - formato="detallado": retorna objeto con más info
    
    Usa asignaciones_examen
    """
    
    try:
        # Query optimizado
        query = text("""
            SELECT 
                a.id,
                a.codigo,
                a.nombre,
                a.piso,
                a.pabellon,
                a.capacidad,
                COUNT(ae.id) as total_asignados,
                MIN(p.apellido_paterno) as primer_apellido,
                MAX(p.apellido_paterno) as ultimo_apellido
            FROM aulas a
            INNER JOIN asignaciones_examen ae ON ae.aula_id = a.id
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.proceso_admision = :proceso
              AND p.activo = true
            GROUP BY a.id, a.codigo, a.nombre, a.piso, a.pabellon, a.capacidad
            ORDER BY a.codigo
        """)
        
        result = db.execute(query, {"proceso": proceso})
        aulas = result.fetchall()
        
        # Formato simple (para listas de control)
        if formato == "simple":
            return [
                {
                    "id": a.id,
                    "codigo": a.codigo,
                    "nombre": a.nombre or "",
                    "total": a.total_asignados
                }
                for a in aulas
            ]
        
        # Formato detallado (para dashboard)
        else:
            resultado = []
            
            for a in aulas:
                # Obtener profesor asignado
                query_profesor = text("""
                    SELECT DISTINCT 
                        prof.dni,
                        prof.apellido_paterno,
                        prof.apellido_materno,
                        prof.nombres
                    FROM asignaciones_examen ae
                    INNER JOIN profesores prof ON ae.profesor_id = prof.id
                    WHERE ae.aula_id = :aula_id
                      AND ae.proceso_admision = :proceso
                    LIMIT 1
                """)
                
                profesor_result = db.execute(query_profesor, {
                    "aula_id": a.id,
                    "proceso": proceso
                }).fetchone()
                
                profesor_info = None
                if profesor_result:
                    profesor_info = {
                        "dni": profesor_result.dni,
                        "nombre": f"{profesor_result.apellido_paterno} {profesor_result.apellido_materno}, {profesor_result.nombres}"
                    }
                
                # Verificar si tiene hojas generadas
                query_hojas = text("""
                    SELECT COUNT(*) 
                    FROM hojas_respuestas 
                    WHERE codigo_aula = :codigo_aula 
                      AND proceso_admision = :proceso
                """)
                
                hojas_count = db.execute(query_hojas, {
                    "codigo_aula": a.codigo,
                    "proceso": proceso
                }).scalar() or 0
                
                resultado.append({
                    "aula_id": a.id,
                    "codigo_aula": a.codigo,
                    "nombre": a.nombre or f"Aula {a.codigo}",
                    "piso": a.piso or "1",
                    "edificio": a.pabellon or "Principal",
                    "capacidad_maxima": a.capacidad or 30,
                    "postulantes_asignados": a.total_asignados,
                    "profesor": profesor_info,
                    "tiene_hojas_generadas": hojas_count > 0,
                    "rango_alfabetico": f"{a.primer_apellido} - {a.ultimo_apellido}" if a.primer_apellido else None
                })
            
            return {
                "success": True,
                "total_aulas": len(resultado),
                "aulas": resultado
            }
        
    except Exception as e:
        print(f"Error en listar_aulas_con_asignaciones: {e}")
        import traceback
        traceback.print_exc()
        
        if formato == "simple":
            raise HTTPException(status_code=500, detail=str(e))
        else:
            return {
                "success": False,
                "total_aulas": 0,
                "aulas": [],
                "error": str(e)
            }

@router.get("/generar-hojas-aula/{aula_id}")
async def generar_hojas_por_aula(
    aula_id: int,
    db: Session = Depends(get_db)
):
    """
    Genera hojas para un aula específica.
    Usa asignaciones_examen
    """
    
    try:
        # Obtener aula
        aula = db.query(Aula).filter(Aula.id == aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        # Obtener postulantes asignados a esta aula
        query = text("""
            SELECT 
                p.id,
                p.codigo_unico,
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                p.programa_educativo,
                ae.id as asignacion_id
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id
              AND p.activo = true
            ORDER BY p.apellido_paterno, p.apellido_materno, p.nombres
        """)
        
        result = db.execute(query, {"aula_id": aula_id})
        asignaciones = result.fetchall()
        
        if not asignaciones:
            raise HTTPException(
                status_code=400,
                detail=f"El aula {aula.codigo} no tiene postulantes asignados"
            )
        
        # Construir lista de postulantes
        postulantes_data = []
        for idx, row in enumerate(asignaciones, 1):
            postulantes_data.append({
                "codigo_postulante": row.codigo_unico or f"POST-{row.id}",
                "dni": row.dni,
                "nombre_completo": f"{row.apellido_paterno} {row.apellido_materno}, {row.nombres}",
                "asiento": idx,  # Número correlativo
                "programa": row.programa_educativo
            })
        
        return {
            "success": True,
            "aula": {
                "codigo": aula.codigo,
                "nombre": aula.nombre or f"Aula {aula.codigo}",
                "ubicacion": f"Pabellón {aula.pabellon} - Piso {aula.piso}",
                "capacidad": aula.capacidad or 30
            },
            "profesor": None,  # No hay profesor en asignaciones_examen
            "postulantes": postulantes_data,
            "total_postulantes": len(postulantes_data),
            "mensaje": "Datos obtenidos correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en generar_hojas_por_aula: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generar-todas-las-aulas")
async def generar_hojas_todas_aulas(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Genera hojas para todas las aulas.
    """
    
    try:
        aulas = db.query(Aula).filter(Aula.activo == True).all()
        
        resultado = []
        
        for aula in aulas:
            query = text("""
                SELECT COUNT(*) 
                FROM asignaciones_examen ae
                INNER JOIN postulantes p ON ae.postulante_id = p.id
                WHERE ae.aula_id = :aula_id
                  AND p.activo = true
                  AND p.proceso_admision = :proceso
            """)
            result = db.execute(query, {"aula_id": aula.id, "proceso": proceso})
            count = result.scalar() or 0
            
            if count > 0:
                resultado.append({
                    "aula_codigo": aula.codigo,
                    "postulantes": count,
                    "pdf_generado": False
                })
        
        return {
            "success": True,
            "total_aulas_procesadas": len(resultado),
            "aulas": resultado,
            "mensaje": "Generación completada (PDFs pendientes de implementar)"
        }
        
    except Exception as e:
        print(f"Error en generar_todas_las_aulas: {e}")
        return {
            "success": False,
            "total_aulas_procesadas": 0,
            "aulas": [],
            "error": str(e)
        }

@router.get("/debug-estructura")
async def debug_estructura(db: Session = Depends(get_db)):
    """
    Endpoint de debug para verificar estructura.
    """
    
    try:
        # Contar en ambas tablas
        query_asignaciones_examen = text("SELECT COUNT(*) FROM asignaciones_examen")
        count_ae = db.execute(query_asignaciones_examen).scalar()
        
        query_postulantes_asignacion = text("SELECT COUNT(*) FROM postulantes_asignacion")
        count_pa = db.execute(query_postulantes_asignacion).scalar()
        
        # Sample de asignaciones_examen
        query_sample = text("""
            SELECT ae.id, ae.postulante_id, ae.aula_id, p.dni, p.nombres
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            LIMIT 5
        """)
        sample = db.execute(query_sample).fetchall()
        
        return {
            "tablas": {
                "asignaciones_examen": count_ae,
                "postulantes_asignacion": count_pa
            },
            "sample_asignaciones_examen": [
                {
                    "id": row.id,
                    "postulante_id": row.postulante_id,
                    "aula_id": row.aula_id,
                    "dni": row.dni,
                    "nombres": row.nombres
                } for row in sample
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}
    


"""
Endpoint de Asignación y Generación Masiva
Agregar a app/api/generar_hojas_aula.py
"""

"""
ENDPOINT MEJORADO - Asignar y Generar Hojas
REEMPLAZAR el endpoint actual en app/api/generar_hojas_aula.py

MEJORAS:
- Commits parciales cada 10 registros
- Progress tracking detallado
- Mejor manejo de archivos temporales
- Validación de ZIP antes de enviar
- Headers optimizados para archivos grandes
"""

"""
ENDPOINT FINAL - Asignar y Generar Hojas
REEMPLAZAR en app/api/generar_hojas_aula.py

CARACTERÍSTICAS:
- Usuario elige: ZIP por aula o ZIP único
- Estructura organizada por carpetas
- Commits parciales
- Progress tracking
"""

@router.post("/asignar-y-generar-hojas")
async def asignar_y_generar_hojas(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Asigna postulantes ALFABÉTICAMENTE y genera hojas.
    
    VERSIÓN 2.0: Con orden alfabético y N° de orden en PDF
    
    Body:
    {
        "proceso_admision": "2025-2",
        "modo_generacion": "individual" | "unico"
    }
    """
    
    import tempfile
    import os
    import zipfile
    import shutil
    from io import BytesIO
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    from app.services.pdf_generator_simple import generar_hoja_generica
    from app.utils import generar_codigo_hoja_unico
    
    temp_dir = None
    
    try:
        proceso = data.get('proceso_admision', '2025-2')
        modo_generacion = data.get('modo_generacion', 'unico')
        
        print(f"\n{'='*70}")
        print(f"🎯 ASIGNACIÓN ALFABÉTICA Y GENERACIÓN MASIVA V2.0")
        print(f"{'='*70}")
        print(f"Proceso: {proceso}")
        print(f"Modo: {modo_generacion}")
        
        # ================================================================
        # 1. EJECUTAR ASIGNACIÓN ALFABÉTICA
        # ================================================================
        
        print(f"\n📝 PASO 1: Asignación alfabética...")
        
        resultado_asignacion = asignar_alfabeticamente(db, proceso)
        
        if not resultado_asignacion["success"]:
            raise HTTPException(
                status_code=400,
                detail=resultado_asignacion.get("message", "Error en asignación")
            )
        
        # Verificar que haya asignaciones
        total_asignados = resultado_asignacion.get('total_asignados', 0)
        aulas_utilizadas = resultado_asignacion.get('aulas_utilizadas', 0)
        
        if total_asignados == 0:
            raise HTTPException(
                status_code=400,
                detail="No se pudo asignar ningún postulante. Verifica que haya postulantes activos sin asignar."
            )
        
        print(f"✅ Asignados: {total_asignados}")
        print(f"✅ Aulas: {aulas_utilizadas}")
        
        # ================================================================
        # 2. OBTENER ASIGNACIONES ORDENADAS
        # ================================================================
        
        print(f"\n📝 PASO 2: Obteniendo asignaciones ordenadas...")
        
        query_asignaciones = text("""
            SELECT 
                ae.id as asignacion_id,
                p.id as postulante_id,
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                a.id as aula_id,
                a.codigo as aula_codigo,
                prof.dni as profesor_dni,
                ae.orden_alfabetico
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            INNER JOIN aulas a ON ae.aula_id = a.id
            INNER JOIN profesores prof ON ae.profesor_id = prof.id
            WHERE p.proceso_admision = :proceso
              AND ae.estado = 'confirmado'
            ORDER BY a.codigo, ae.orden_alfabetico
        """)
        
        result = db.execute(query_asignaciones, {"proceso": proceso})
        asignaciones = result.fetchall()
        
        if not asignaciones:
            raise HTTPException(
                status_code=400,
                detail="No hay asignaciones confirmadas"
            )
        
        print(f"✅ Total asignaciones: {len(asignaciones)}")
        
        # ================================================================
        # 3. CREAR DIRECTORIO TEMPORAL
        # ================================================================
        
        temp_dir = tempfile.mkdtemp()
        os.makedirs("uploads/hojas_generadas", exist_ok=True)
        
        archivos_por_aula = []
        todos_los_pdfs = []
        
        # Agrupar por aula
        aulas_dict = {}
        for asig in asignaciones:
            aula_codigo = asig.aula_codigo
            if aula_codigo not in aulas_dict:
                aulas_dict[aula_codigo] = []
            aulas_dict[aula_codigo].append(asig)
        
        print(f"\n📝 PASO 3: Generando PDFs con N° de orden...")
        print(f"Aulas a procesar: {len(aulas_dict)}")
        
        # ================================================================
        # 4. GENERAR PDFs POR AULA (CON ORDEN)
        # ================================================================
        
        for idx_aula, (aula_codigo, asignaciones_aula) in enumerate(aulas_dict.items(), 1):
            print(f"\n{'='*70}")
            print(f"📦 AULA {idx_aula}/{len(aulas_dict)}: {aula_codigo}")
            print(f"   Cantidad: {len(asignaciones_aula)}")
            print(f"{'='*70}")
            
            # Crear subdirectorio por aula
            aula_dir = os.path.join(temp_dir, aula_codigo)
            os.makedirs(aula_dir, exist_ok=True)
            
            pdf_files_aula = []
            
            for asig in asignaciones_aula:
                try:
                    # Generar código único
                    codigo_hoja = generar_codigo_hoja_unico()
                    
                    intentos = 0
                    while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                        codigo_hoja = generar_codigo_hoja_unico()
                        intentos += 1
                        if intentos > 10:
                            raise Exception("No se pudo generar código único")
                    
                    # ============================================================
                    # CREAR HOJA CON ORDEN_AULA
                    # ============================================================
                    
                    hoja = HojaRespuesta(
                        postulante_id=asig.postulante_id,
                        dni_profesor=asig.profesor_dni,
                        codigo_aula=aula_codigo,
                        codigo_hoja=codigo_hoja,
                        proceso_admision=proceso,
                        estado="generada",
                        orden_aula=asig.orden_alfabetico  # ← GUARDAR ORDEN
                    )
                    db.add(hoja)
                    
                    # ============================================================
                    # GENERAR PDF CON ORDEN_AULA
                    # ============================================================
                    
                    filename = f"hoja_{asig.dni}_{codigo_hoja}.pdf"
                    filepath = os.path.join(aula_dir, filename)
                    
                    generar_hoja_generica(
                        output_path=filepath,
                        numero_hoja=asig.orden_alfabetico,
                        codigo_hoja=codigo_hoja,
                        proceso=proceso,
                        descripcion="Examen de Admisión"
                    )
                    
                    if not os.path.exists(filepath):
                        raise Exception(f"PDF no generado: {filename}")
                    
                    pdf_files_aula.append(filepath)
                    todos_los_pdfs.append(filepath)
                    
                    # Commit parcial cada 10
                    if len(todos_los_pdfs) % 10 == 0:
                        db.commit()
                        print(f"   💾 Commit parcial: {len(todos_los_pdfs)} hojas")
                
                except Exception as e:
                    print(f"   ❌ ERROR: {str(e)}")
                    raise
            
            print(f"✅ Aula {aula_codigo}: {len(pdf_files_aula)} hojas generadas")
            
            # ============================================================
            # CREAR ZIP POR AULA (modo individual)
            # ============================================================
            
            if modo_generacion == 'individual':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                zip_filename = f"hojas_{aula_codigo}_{timestamp}.zip"
                zip_path = os.path.join("uploads/hojas_generadas", zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for pdf_file in pdf_files_aula:
                        arcname = os.path.basename(pdf_file)
                        zip_file.write(pdf_file, arcname)
                
                archivos_por_aula.append({
                    "aula": aula_codigo,
                    "cantidad": len(pdf_files_aula),
                    "archivo": zip_filename,
                    "url_descarga": f"/uploads/hojas_generadas/{zip_filename}",
                    "tamanio_mb": round(os.path.getsize(zip_path) / (1024*1024), 2)
                })
                
                print(f"   📦 ZIP creado: {zip_filename}")
        
        # ================================================================
        # 5. COMMIT FINAL
        # ================================================================
        
        db.commit()
        print(f"\n✅ COMMIT FINAL: {len(todos_los_pdfs)} hojas registradas en BD")
        
        # ================================================================
        # 6. RETORNAR SEGÚN MODO
        # ================================================================
        
        if modo_generacion == 'individual':
            # Modo individual: retornar JSON con URLs
            shutil.rmtree(temp_dir)
            
            return {
                "success": True,
                "modo": "individual",
                "total_hojas": len(todos_los_pdfs),
                "total_aulas": len(archivos_por_aula),
                "archivos": archivos_por_aula,
                "mensaje": f"Se generaron {len(archivos_por_aula)} archivos ZIP (uno por aula) con orden alfabético"
            }
        
        else:
            # Modo único: retornar ZIP con todo
            print(f"\n📦 Creando ZIP único...")
            
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_file in todos_los_pdfs:
                    arcname = os.path.relpath(pdf_file, temp_dir)
                    zip_file.write(pdf_file, arcname)
            
            zip_buffer.seek(0)
            zip_size = len(zip_buffer.getvalue())
            
            shutil.rmtree(temp_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hojas_{proceso}_{timestamp}.zip"
            
            print(f"\n✅ ZIP único creado: {filename}")
            print(f"   Tamaño: {zip_size / (1024*1024):.2f} MB")
            print(f"   Total hojas: {len(todos_los_pdfs)}\n")
            
            return StreamingResponse(
                iter([zip_buffer.getvalue()]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(zip_size),
                    "X-Total-Hojas": str(len(todos_los_pdfs)),
                    "Cache-Control": "no-cache"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=str(e))



"""
Endpoint para REGENERAR hojas usando asignaciones existentes
Agregar a app/api/generar_hojas_aula.py
"""

@router.post("/regenerar-hojas-desde-asignaciones")
async def regenerar_hojas_desde_asignaciones(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Regenera las hojas de respuestas usando las asignaciones YA EXISTENTES.
    
    NO vuelve a asignar, solo genera nuevos PDFs con nuevos códigos.
    
    Body:
    {
        "proceso_admision": "2025-2",
        "modo_generacion": "unico" | "individual"
    }
    """
    
    import tempfile
    import os
    import zipfile
    import shutil
    from io import BytesIO
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    from app.services.pdf_generator_v3 import generar_hoja_respuestas_v3
    from app.utils import generar_codigo_hoja_unico
    
    temp_dir = None
    
    try:
        proceso = data.get('proceso_admision', '2025-2')
        modo_generacion = data.get('modo_generacion', 'unico')
        
        print(f"\n{'='*70}")
        print(f"🔄 REGENERACIÓN DE HOJAS DESDE ASIGNACIONES EXISTENTES")
        print(f"{'='*70}")
        print(f"Proceso: {proceso}")
        print(f"Modo: {modo_generacion}")
        
        # ================================================================
        # 1. OBTENER ASIGNACIONES EXISTENTES
        # ================================================================
        
        query_asignaciones = text("""
            SELECT 
                ae.id as asignacion_id,
                p.id as postulante_id,
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                a.id as aula_id,
                a.codigo as aula_codigo,
                prof.dni as profesor_dni
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            INNER JOIN aulas a ON ae.aula_id = a.id
            INNER JOIN profesores prof ON ae.profesor_id = prof.id
            WHERE p.proceso_admision = :proceso
              AND ae.estado = 'confirmado'
            ORDER BY a.codigo, p.apellido_paterno, p.apellido_materno
        """)
        
        result = db.execute(query_asignaciones, {"proceso": proceso})
        asignaciones = result.fetchall()
        
        if not asignaciones:
            raise HTTPException(
                status_code=400,
                detail="No hay asignaciones confirmadas en el proceso."
            )
        
        print(f"✅ Asignaciones encontradas: {len(asignaciones)}")
        
        # ================================================================
        # 2. CREAR DIRECTORIO TEMPORAL
        # ================================================================
        
        temp_dir = tempfile.mkdtemp()
        os.makedirs("uploads/hojas_generadas", exist_ok=True)
        
        archivos_por_aula = []
        todos_los_pdfs = []
        
        # Agrupar por aula
        aulas_dict = {}
        for asig in asignaciones:
            aula_codigo = asig.aula_codigo
            if aula_codigo not in aulas_dict:
                aulas_dict[aula_codigo] = []
            aulas_dict[aula_codigo].append(asig)
        
        print(f"📦 Aulas a procesar: {len(aulas_dict)}")
        
        # ================================================================
        # 3. GENERAR PDFs POR AULA
        # ================================================================
        
        for idx, (aula_codigo, asignaciones_aula) in enumerate(aulas_dict.items(), 1):
            print(f"\n{'='*70}")
            print(f"📦 AULA {idx}/{len(aulas_dict)}: {aula_codigo}")
            print(f"   Cantidad: {len(asignaciones_aula)}")
            print(f"{'='*70}")
            
            # Crear subdirectorio por aula
            aula_dir = os.path.join(temp_dir, aula_codigo)
            os.makedirs(aula_dir, exist_ok=True)
            
            pdf_files_aula = []
            
            for asig in asignaciones_aula:
                try:
                    # Generar código único
                    codigo_hoja = generar_codigo_hoja_unico()
                    
                    intentos = 0
                    while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                        codigo_hoja = generar_codigo_hoja_unico()
                        intentos += 1
                        if intentos > 10:
                            raise Exception("No se pudo generar código único")
                    
                    # Crear nuevo registro de hoja
                    hoja = HojaRespuesta(
                        postulante_id=asig.postulante_id,
                        dni_profesor=asig.profesor_dni,
                        codigo_aula=aula_codigo,
                        codigo_hoja=codigo_hoja,
                        proceso_admision=proceso,
                        estado="generada"
                    )
                    db.add(hoja)
                    
                    # Generar PDF
                    filename = f"hoja_{asig.dni}_{codigo_hoja}.pdf"
                    filepath = os.path.join(aula_dir, filename)
                    
                    generar_hoja_respuestas_v3(
                        output_path=filepath,
                        dni_postulante=asig.dni,
                        codigo_aula=aula_codigo,
                        dni_profesor=asig.profesor_dni,
                        codigo_hoja=codigo_hoja,
                        proceso=proceso
                    )
                    
                    if not os.path.exists(filepath):
                        raise Exception(f"PDF no generado: {filename}")
                    
                    pdf_files_aula.append(filepath)
                    todos_los_pdfs.append(filepath)
                    
                    # Commit parcial cada 10
                    if len(todos_los_pdfs) % 10 == 0:
                        db.commit()
                        print(f"   💾 Commit parcial: {len(todos_los_pdfs)} hojas")
                
                except Exception as e:
                    print(f"   ❌ ERROR en {asig.dni}: {str(e)}")
                    raise
            
            print(f"✅ Aula {aula_codigo}: {len(pdf_files_aula)} hojas regeneradas")
            
            # Crear ZIP por aula (modo individual)
            if modo_generacion == 'individual':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                zip_filename = f"hojas_{aula_codigo}_{timestamp}.zip"
                zip_path = os.path.join("uploads/hojas_generadas", zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for pdf_file in pdf_files_aula:
                        arcname = os.path.basename(pdf_file)
                        zip_file.write(pdf_file, arcname)
                
                archivos_por_aula.append({
                    "aula": aula_codigo,
                    "cantidad": len(pdf_files_aula),
                    "archivo": zip_filename,
                    "url_descarga": f"/uploads/hojas_generadas/{zip_filename}",
                    "tamanio_mb": round(os.path.getsize(zip_path) / (1024*1024), 2)
                })
        
        # ================================================================
        # 4. COMMIT FINAL
        # ================================================================
        
        db.commit()
        print(f"\n✅ COMMIT FINAL: {len(todos_los_pdfs)} hojas regeneradas")
        
        # ================================================================
        # 5. RETORNAR SEGÚN MODO
        # ================================================================
        
        if modo_generacion == 'individual':
            shutil.rmtree(temp_dir)
            
            return {
                "success": True,
                "modo": "individual",
                "total_hojas": len(todos_los_pdfs),
                "total_aulas": len(archivos_por_aula),
                "archivos": archivos_por_aula,
                "mensaje": f"Se regeneraron {len(archivos_por_aula)} archivos ZIP"
            }
        
        else:
            print(f"\n📦 Creando ZIP único...")
            
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_file in todos_los_pdfs:
                    arcname = os.path.relpath(pdf_file, temp_dir)
                    zip_file.write(pdf_file, arcname)
            
            zip_buffer.seek(0)
            zip_size = len(zip_buffer.getvalue())
            
            shutil.rmtree(temp_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hojas_regeneradas_{proceso}_{timestamp}.zip"
            
            print(f"\n✅ ZIP único creado: {filename}")
            print(f"   Tamaño: {zip_size / (1024*1024):.2f} MB\n")
            
            return StreamingResponse(
                iter([zip_buffer.getvalue()]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(zip_size),
                    "X-Total-Hojas": str(len(todos_los_pdfs)),
                    "Cache-Control": "no-cache"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lista-control-aula/{aula_id}")
async def generar_lista_control_aula(
    aula_id: int,
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Lista de control OPTIMIZADA para fotografía y Vision API.
    
    VERSIÓN 3.0:
    - Sin instrucciones (caben más filas en A4)
    - Checkbox para marcar SOLO ausentes
    - Columnas: N° Orden | ✅ NO ASISTIÓ | DNI | Apellidos y Nombres | Firma
    - Sin código de hoja ni programa (redundantes)
    - Layout optimizado para A4 vertical
    """
    
    from fastapi.responses import HTMLResponse
    from datetime import datetime
    
    try:
        # Obtener aula
        aula = db.query(Aula).filter_by(id=aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        # Obtener profesor
        query_profesor = text("""
            SELECT DISTINCT 
                prof.dni, 
                prof.nombres, 
                prof.apellido_paterno, 
                prof.apellido_materno
            FROM asignaciones_examen ae
            JOIN profesores prof ON ae.profesor_id = prof.id
            WHERE ae.aula_id = :aula_id 
              AND ae.proceso_admision = :proceso
            LIMIT 1
        """)
        profesor = db.execute(query_profesor, {"aula_id": aula_id, "proceso": proceso}).fetchone()
        
        profesor_nombre = "SIN ASIGNAR"
        profesor_dni = ""
        if profesor:
            profesor_nombre = f"{profesor.apellido_paterno} {profesor.apellido_materno}, {profesor.nombres}"
            profesor_dni = profesor.dni
        
        # Obtener postulantes ordenados
        query_postulantes = text("""
            SELECT 
                ae.orden_alfabetico,
                p.dni,
                p.apellido_paterno,
                p.apellido_materno,
                p.nombres
            FROM asignaciones_examen ae
            JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id 
              AND ae.proceso_admision = :proceso
            ORDER BY ae.orden_alfabetico
        """)
        
        result = db.execute(query_postulantes, {"aula_id": aula_id, "proceso": proceso})
        postulantes = result.fetchall()
        
        fecha_actual = datetime.now().strftime('%d/%m/%Y')
        
        # ====================================================================
        # HTML OPTIMIZADO PARA A4
        # ====================================================================
        
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Lista de Control - {aula.codigo}</title>
            <style>
                @page {{
                    size: A4 portrait;
                    margin: 10mm;
                }}
                
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Arial', sans-serif;
                    font-size: 9px;
                    line-height: 1.2;
                    color: #000;
                }}
                
                .header {{
                    text-align: center;
                    border: 2px solid #000;
                    padding: 8px;
                    margin-bottom: 8px;
                    background: #f8f9fa;
                }}
                
                .header h1 {{
                    font-size: 14px;
                    font-weight: bold;
                    margin-bottom: 2px;
                }}
                
                .header .institucion {{
                    font-size: 10px;
                    font-weight: bold;
                    margin-bottom: 4px;
                }}
                
                .header .proceso {{
                    font-size: 11px;
                    font-weight: bold;
                    margin-top: 2px;
                }}
                
                .info-aula {{
                    display: grid;
                    grid-template-columns: 1fr 1fr 1fr;
                    gap: 6px;
                    margin: 6px 0;
                    padding: 6px;
                    background: #e9ecef;
                    border: 1px solid #495057;
                    font-size: 9px;
                }}
                
                .info-item {{
                    font-size: 9px;
                }}
                
                .info-item strong {{
                    font-weight: bold;
                }}
                
                .alert-box {{
                    background: #fff3cd;
                    border: 2px solid #ffc107;
                    padding: 6px;
                    margin: 6px 0;
                    text-align: center;
                    font-size: 9px;
                    font-weight: bold;
                    color: #856404;
                }}
                
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 6px 0;
                }}
                
                th, td {{
                    border: 1px solid #000;
                    padding: 4px 3px;
                    text-align: left;
                }}
                
                th {{
                    background: #343a40;
                    color: #fff;
                    font-weight: bold;
                    font-size: 8px;
                    text-align: center;
                    padding: 5px 3px;
                }}
                
                td {{
                    font-size: 8px;
                }}
                
                .col-orden {{
                    width: 6%;
                    text-align: center;
                }}
                
                .col-check {{
                    width: 7%;
                    text-align: center;
                }}
                
                .col-dni {{
                    width: 11%;
                    font-family: 'Courier New', monospace;
                    font-size: 9px;
                }}
                
                .col-nombre {{
                    width: 50%;
                }}
                
                .col-firma {{
                    width: 26%;
                    background: #f8f9fa;
                }}
                
                .orden-circulo {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 20px;
                    height: 20px;
                    border: 2px solid #000;
                    border-radius: 50%;
                    font-weight: bold;
                    font-size: 9px;
                }}
                
                .checkbox {{
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    border: 2px solid #000;
                    margin: 0 auto;
                    background: #fff;
                }}
                
                .firma-section {{
                    margin-top: 15px;
                    page-break-inside: avoid;
                }}
                
                .firma-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin-top: 30px;
                }}
                
                .firma-box {{
                    text-align: center;
                }}
                
                .firma-line {{
                    border-top: 2px solid #000;
                    margin-top: 40px;
                    padding-top: 4px;
                    font-size: 9px;
                    font-weight: bold;
                }}
                
                .footer {{
                    margin-top: 8px;
                    padding: 4px;
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    font-size: 7px;
                    text-align: center;
                    color: #6c757d;
                }}
                
                @media print {{
                    body {{
                        print-color-adjust: exact;
                        -webkit-print-color-adjust: exact;
                    }}
                }}
            </style>
        </head>
        <body>
            <!-- HEADER -->
            <div class="header">
                <h1>📋 LISTA DE CONTROL DE ASISTENCIA</h1>
                <div class="institucion">I.S.T. Pedro A. Del Águila Hidalgo</div>
                <div class="proceso">PROCESO {proceso} - EXAMEN DE ADMISIÓN</div>
            </div>
            
            <!-- INFO DEL AULA -->
            <div class="info-aula">
                <div class="info-item">
                    <strong>🏫 AULA:</strong> {aula.codigo} {('- ' + aula.nombre) if aula.nombre else ''}
                </div>
                <div class="info-item">
                    <strong>👨‍🏫 PROFESOR:</strong> {profesor_nombre}
                </div>
                <div class="info-item">
                    <strong>📅 FECHA:</strong> {fecha_actual}
                </div>
            </div>
            
            <!-- ALERTA -->
            <div class="alert-box">
                ⚠️ MARQUE CON X o ✓ EN EL RECUADRO "✅ NO ASISTIÓ" SOLO LOS POSTULANTES AUSENTES | TOME FOTO CLARA AL FINALIZAR
            </div>
            
            <!-- TABLA -->
            <table>
                <thead>
                    <tr>
                        <th class="col-orden">N°<br>ORDEN</th>
                        <th class="col-check">✅<br>NO ASISTIÓ</th>
                        <th class="col-dni">DNI</th>
                        <th class="col-nombre">APELLIDOS Y NOMBRES</th>
                        <th class="col-firma">FIRMA DEL POSTULANTE</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # ====================================================================
        # FILAS DE POSTULANTES
        # ====================================================================
        
        for p in postulantes:
            nombre_completo = f"{p.apellido_paterno} {p.apellido_materno}, {p.nombres}"
            
            html += f"""
                    <tr>
                        <td class="col-orden">
                            <div class="orden-circulo">{p.orden_alfabetico:02d}</div>
                        </td>
                        <td class="col-check">
                            <div class="checkbox"></div>
                        </td>
                        <td class="col-dni">{p.dni}</td>
                        <td class="col-nombre">{nombre_completo}</td>
                        <td class="col-firma"></td>
                    </tr>
            """
        
        # ====================================================================
        # FIRMAS Y FOOTER
        # ====================================================================
        
        html += f"""
                </tbody>
            </table>
            
            <!-- FIRMAS -->
            <div class="firma-section">
                <div class="firma-grid">
                    <div class="firma-box">
                        <div class="firma-line">
                            Firma del Profesor Vigilante<br>
                            {profesor_nombre}<br>
                            DNI: {profesor_dni if profesor_dni else '_______________'}
                        </div>
                    </div>
                    <div class="firma-box">
                        <div class="firma-line">
                            Hora inicio: _______ | Hora fin: _______<br>
                            Total presentes: _______ de {len(postulantes)}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- FOOTER -->
            <div class="footer">
                POSTULANDO | Generado: {fecha_actual} | Aula: {aula.codigo} | Proceso: {proceso}
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        print(f"❌ Error generando lista: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/limpiar-proceso")
async def limpiar_proceso(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Limpia asignaciones y hojas de un proceso para poder regenerar.
    
    Body:
    {
        "proceso_admision": "2025-2",
        "confirmar": true
    }
    """
    
    try:
        proceso = data.get('proceso_admision', '2025-2')
        confirmar = data.get('confirmar', False)
        
        if not confirmar:
            raise HTTPException(
                status_code=400,
                detail="Debe confirmar la limpieza explícitamente"
            )
        
        print(f"\n{'='*70}")
        print(f"🗑️  LIMPIEZA DE PROCESO: {proceso}")
        print(f"{'='*70}")
        
        # 1. Contar registros a eliminar
        query_count_asignaciones = text("""
            SELECT COUNT(*) FROM asignaciones_examen 
            WHERE proceso_admision = :proceso
        """)
        total_asignaciones = db.execute(query_count_asignaciones, {"proceso": proceso}).scalar()
        
        query_count_hojas = text("""
            SELECT COUNT(*) FROM hojas_respuestas 
            WHERE proceso_admision = :proceso
        """)
        total_hojas = db.execute(query_count_hojas, {"proceso": proceso}).scalar()
        
        query_count_respuestas = text("""
            SELECT COUNT(*) FROM respuestas r
            INNER JOIN hojas_respuestas hr ON r.hoja_respuesta_id = hr.id
            WHERE hr.proceso_admision = :proceso
        """)
        total_respuestas = db.execute(query_count_respuestas, {"proceso": proceso}).scalar()
        
        print(f"📊 Registros a eliminar:")
        print(f"   - Asignaciones: {total_asignaciones}")
        print(f"   - Hojas: {total_hojas}")
        print(f"   - Respuestas: {total_respuestas}")
        
        # 2. Eliminar registros
        print(f"\n🗑️  Eliminando...")
        
        # Respuestas individuales
        db.execute(text("""
            DELETE FROM respuestas 
            WHERE hoja_respuesta_id IN (
                SELECT id FROM hojas_respuestas 
                WHERE proceso_admision = :proceso
            )
        """), {"proceso": proceso})
        
        # Hojas de respuesta
        db.execute(text("""
            DELETE FROM hojas_respuestas 
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso})
        
        # Asignaciones
        db.execute(text("""
            DELETE FROM asignaciones_examen 
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso})
        
        # Resetear postulantes
        db.execute(text("""
            UPDATE postulantes 
            SET examen_rendido = false,
                aula_id = NULL
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso})
        
        db.commit()
        
        print(f"✅ Limpieza completada")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "mensaje": f"Proceso {proceso} limpiado correctamente",
            "eliminados": {
                "asignaciones": total_asignaciones,
                "hojas": total_hojas,
                "respuestas": total_respuestas
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error en limpieza: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

# ================================================================
# PARA FORMULARIO DE ASISTENCIAS EN DASHBOARD COORDINADOR/PROFESOR
# ================================================================
"""
ENDPOINTS PARA REGISTRO DE ASISTENCIA
"""

from pydantic import BaseModel
from typing import List

class RegistroAsistenciaRequest(BaseModel):
    aula_id: int
    proceso_admision: str
    ausentes_dni: List[str]  # Lista de DNIs de postulantes ausentes
    registrado_por: str  # Usuario que registra

@router.post("/registrar-asistencia")
async def registrar_asistencia(
    data: RegistroAsistenciaRequest,
    db: Session = Depends(get_db)
):
    """
    Registra la asistencia de un aula.
    
    LÓGICA:
    - Por defecto todos asistieron
    - Se marca solo los ausentes
    - Se actualiza campo 'asistio' en asignaciones_examen
    """
    
    try:
        from datetime import datetime
        
        print(f"\n{'='*70}")
        print(f"📝 REGISTRO DE ASISTENCIA")
        print(f"{'='*70}")
        print(f"Aula ID: {data.aula_id}")
        print(f"Proceso: {data.proceso_admision}")
        print(f"Ausentes: {len(data.ausentes_dni)}")
        print(f"Registrado por: {data.registrado_por}")
        
        # Verificar que el aula existe
        aula = db.query(Aula).filter_by(id=data.aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        # Obtener todos los postulantes del aula
        query_postulantes = text("""
            SELECT 
                ae.id as asignacion_id,
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id
              AND ae.proceso_admision = :proceso
        """)
        
        result = db.execute(query_postulantes, {
            "aula_id": data.aula_id,
            "proceso": data.proceso_admision
        })
        asignaciones = result.fetchall()
        
        if not asignaciones:
            raise HTTPException(
                status_code=400,
                detail="No hay postulantes asignados a esta aula"
            )
        
        total_postulantes = len(asignaciones)
        print(f"Total postulantes en aula: {total_postulantes}")
        
        # Marcar TODOS como presentes (por defecto)
        query_update_presentes = text("""
            UPDATE asignaciones_examen
            SET asistio = true,
                hora_registro_asistencia = NOW(),
                registrado_por = :registrado_por
            WHERE aula_id = :aula_id
              AND proceso_admision = :proceso
        """)
        
        db.execute(query_update_presentes, {
            "aula_id": data.aula_id,
            "proceso": data.proceso_admision,
            "registrado_por": data.registrado_por
        })
        
        print(f"✅ Todos marcados como PRESENTES")
        
        # Marcar los AUSENTES
        ausentes_registrados = 0
        
        if data.ausentes_dni:
            for dni in data.ausentes_dni:
                query_update_ausente = text("""
                    UPDATE asignaciones_examen ae
                    SET asistio = false,
                        hora_registro_asistencia = NOW(),
                        registrado_por = :registrado_por
                    FROM postulantes p
                    WHERE ae.postulante_id = p.id
                      AND p.dni = :dni
                      AND ae.aula_id = :aula_id
                      AND ae.proceso_admision = :proceso
                """)
                
                result = db.execute(query_update_ausente, {
                    "dni": dni,
                    "aula_id": data.aula_id,
                    "proceso": data.proceso_admision,
                    "registrado_por": data.registrado_por
                })
                
                if result.rowcount > 0:
                    ausentes_registrados += 1
                    print(f"  ❌ Ausente: {dni}")
        
        # Commit
        db.commit()
        
        total_presentes = total_postulantes - ausentes_registrados
        
        print(f"\n📊 RESUMEN:")
        print(f"  Total: {total_postulantes}")
        print(f"  Presentes: {total_presentes}")
        print(f"  Ausentes: {ausentes_registrados}")
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "mensaje": "Asistencia registrada correctamente",
            "aula_codigo": aula.codigo,
            "total_postulantes": total_postulantes,
            "total_presentes": total_presentes,
            "total_ausentes": ausentes_registrados,
            "registrado_por": data.registrado_por,
            "hora_registro": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/obtener-postulantes-aula/{aula_id}")
async def obtener_postulantes_aula(
    aula_id: int,
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de postulantes de un aula para el formulario de asistencia.
    
    Retorna:
    - Lista ordenada alfabéticamente
    - Estado actual de asistencia (si ya fue registrado)
    """
    
    try:
        # Verificar aula
        aula = db.query(Aula).filter_by(id=aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        # Obtener postulantes con estado de asistencia
        query = text("""
            SELECT 
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                ae.orden_alfabetico,
                ae.asistio,
                ae.hora_registro_asistencia,
                ae.registrado_por
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id
              AND ae.proceso_admision = :proceso
            ORDER BY ae.orden_alfabetico
        """)
        
        result = db.execute(query, {"aula_id": aula_id, "proceso": proceso})
        postulantes = result.fetchall()
        
        if not postulantes:
            raise HTTPException(
                status_code=400,
                detail="No hay postulantes asignados a esta aula"
            )
        
        # Verificar si ya fue registrada la asistencia
        asistencia_registrada = any(p.hora_registro_asistencia is not None for p in postulantes)
        
        postulantes_data = []
        for p in postulantes:
            postulantes_data.append({
                "dni": p.dni,
                "nombres": p.nombres,
                "apellido_paterno": p.apellido_paterno,
                "apellido_materno": p.apellido_materno,
                "nombre_completo": f"{p.apellido_paterno} {p.apellido_materno}, {p.nombres}",
                "orden": p.orden_alfabetico,
                "asistio": p.asistio if p.asistio is not None else True,  # Por defecto True
            })
        
        return {
            "success": True,
            "aula": {
                "id": aula.id,
                "codigo": aula.codigo,
                "nombre": aula.nombre or f"Aula {aula.codigo}"
            },
            "postulantes": postulantes_data,
            "total_postulantes": len(postulantes_data),
            "asistencia_registrada": asistencia_registrada,
            "hora_ultimo_registro": postulantes[0].hora_registro_asistencia.isoformat() if postulantes[0].hora_registro_asistencia else None,
            "registrado_por": postulantes[0].registrado_por if postulantes[0].registrado_por else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
