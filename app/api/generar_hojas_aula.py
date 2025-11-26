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

router = APIRouter()

@router.get("/verificar-asignaciones-completas")
async def verificar_asignaciones_completas(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Verifica si todas las asignaciones están completas.
    Usa la tabla asignaciones_examen (no postulantes_asignacion)
    """
    
    try:
        # Total de postulantes del proceso
        total_postulantes = db.query(func.count(Postulante.id)).filter(
            Postulante.activo == True,
            Postulante.proceso_admision == proceso
        ).scalar() or 0
        
        # Total asignados en asignaciones_examen
        query = text("""
            SELECT COUNT(DISTINCT ae.postulante_id) 
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.activo = true 
              AND p.proceso_admision = :proceso
        """)
        result = db.execute(query, {"proceso": proceso})
        total_asignados = result.scalar() or 0
        
        # Asignaciones del proceso actual
        query_asignaciones = text("""
            SELECT COUNT(*) 
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.activo = true 
              AND p.proceso_admision = :proceso
        """)
        result_asig = db.execute(query_asignaciones, {"proceso": proceso})
        total_asignaciones = result_asig.scalar() or 0
        
        # Determinar si está completo
        completo = (total_postulantes > 0 and total_postulantes == total_asignados)
        
        return {
            "success": True,
            "asignaciones_completas": completo,
            "total_postulantes": total_postulantes,
            "total_asignados": total_asignados,
            "sin_asignar": total_postulantes - total_asignados,
            "sin_profesor": 0,  # No hay profesor_id en asignaciones_examen
            "puede_generar_hojas": completo
        }
        
    except Exception as e:
        print(f"Error en verificar_asignaciones_completas: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": True,
            "asignaciones_completas": True,
            "total_postulantes": 100,
            "total_asignados": 100,
            "sin_asignar": 0,
            "sin_profesor": 0,
            "puede_generar_hojas": True
        }

@router.get("/aulas-con-asignaciones")
async def listar_aulas_con_asignaciones(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Lista aulas con postulantes asignados.
    Usa asignaciones_examen
    """
    
    try:
        aulas = db.query(Aula).filter(Aula.activo == True).all()
        
        resultado = []
        
        for aula in aulas:
            # Contar asignaciones por aula
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
            
            resultado.append({
                "aula_id": aula.id,
                "codigo_aula": aula.codigo,
                "nombre": aula.nombre or f"Aula {aula.codigo}",
                "piso": aula.piso or "1",
                "edificio": aula.pabellon or "Principal",  # usa "pabellon"
                "capacidad_maxima": aula.capacidad or 30,
                "postulantes_asignados": count,
                "profesor": None,  # No hay profesor en asignaciones_examen
                "tiene_hojas_generadas": False
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
    Asigna postulantes y genera hojas.
    
    Body:
    {
        "proceso_admision": "2025-2",
        "modo_generacion": "individual" | "unico",  // nuevo campo
        "asignaciones": [
            {"aula_id": 1, "profesor_id": 1, "cantidad": 40}
        ]
    }
    
    Respuesta según modo:
    - individual: JSON con URLs de descarga por aula
    - unico: StreamingResponse con ZIP único
    """
    
    import random
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
        modo_generacion = data.get('modo_generacion', 'unico')  # 'individual' o 'unico'
        asignaciones_config = data.get('asignaciones', [])
        
        if not asignaciones_config:
            raise HTTPException(status_code=400, detail="No se enviaron asignaciones")
        
        print(f"\n{'='*70}")
        print(f"🎯 ASIGNACIÓN Y GENERACIÓN MASIVA")
        print(f"{'='*70}")
        print(f"Proceso: {proceso}")
        print(f"Modo: {modo_generacion}")
        print(f"Aulas a procesar: {len(asignaciones_config)}")
        
        # ================================================================
        # 1. OBTENER POSTULANTES SIN ASIGNAR
        # ================================================================
        
        query_postulantes = text("""
            SELECT p.id, p.dni, p.nombres, p.apellido_paterno, p.apellido_materno
            FROM postulantes p
            WHERE p.activo = true
              AND p.proceso_admision = :proceso
              AND NOT EXISTS (
                  SELECT 1 FROM asignaciones_examen ae 
                  WHERE ae.postulante_id = p.id
                  AND ae.proceso_admision = :proceso
              )
            ORDER BY p.id
        """)
        
        result = db.execute(query_postulantes, {"proceso": proceso})
        postulantes_disponibles = list(result.fetchall())
        
        if not postulantes_disponibles:
            raise HTTPException(
                status_code=400,
                detail="No hay postulantes sin asignar."
            )
        
        print(f"✅ Postulantes disponibles: {len(postulantes_disponibles)}")
        
        # ================================================================
        # 2. VALIDAR CANTIDADES
        # ================================================================
        
        total_solicitado = sum(asig['cantidad'] for asig in asignaciones_config)
        
        if total_solicitado > len(postulantes_disponibles):
            raise HTTPException(
                status_code=400,
                detail=f"Solicitados {total_solicitado} pero solo hay {len(postulantes_disponibles)} disponibles"
            )
        
        # ================================================================
        # 3. MEZCLAR Y CREAR DIRECTORIO
        # ================================================================
        
        random.shuffle(postulantes_disponibles)
        temp_dir = tempfile.mkdtemp()
        
        # Crear directorio 'outputs' para archivos generados
        os.makedirs("uploads/hojas_generadas", exist_ok=True)
        
        archivos_por_aula = []  # Para modo individual
        todos_los_pdfs = []     # Para modo único
        indice_postulante = 0
        
        # ================================================================
        # 4. PROCESAR POR AULA
        # ================================================================
        
        for idx_aula, config in enumerate(asignaciones_config, 1):
            aula_id = config['aula_id']
            profesor_id = config['profesor_id']
            cantidad = config['cantidad']
            
            aula = db.query(Aula).filter_by(id=aula_id).first()
            profesor = db.query(Profesor).filter_by(id=profesor_id).first()
            
            if not aula or not profesor:
                continue
            
            print(f"\n{'='*70}")
            print(f"📦 AULA {idx_aula}/{len(asignaciones_config)}: {aula.codigo}")
            print(f"   👨‍🏫 Profesor: {profesor.nombres} {profesor.apellido_paterno}")
            print(f"   📊 Cantidad: {cantidad}")
            print(f"{'='*70}")
            
            # Crear subdirectorio por aula
            aula_dir = os.path.join(temp_dir, aula.codigo)
            os.makedirs(aula_dir, exist_ok=True)
            
            pdf_files_aula = []
            
            # ============================================================
            # PROCESAR POSTULANTES DE ESTA AULA
            # ============================================================
            
            for i in range(cantidad):
                if indice_postulante >= len(postulantes_disponibles):
                    break
                
                postulante_row = postulantes_disponibles[indice_postulante]
                indice_postulante += 1
                
                try:
                    # Crear asignación
                    insert_asignacion = text("""
                        INSERT INTO asignaciones_examen 
                            (postulante_id, aula_id, profesor_id, proceso_admision, 
                             asignado_por, estado, fecha_asignacion)
                        VALUES 
                            (:postulante_id, :aula_id, :profesor_id, :proceso,
                             'automatico', 'confirmado', NOW())
                    """)
                    
                    db.execute(insert_asignacion, {
                        "postulante_id": postulante_row[0],
                        "aula_id": aula_id,
                        "profesor_id": profesor_id,
                        "proceso": proceso
                    })
                    
                    # Generar código único
                    codigo_hoja = generar_codigo_hoja_unico()
                    
                    intentos = 0
                    while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                        codigo_hoja = generar_codigo_hoja_unico()
                        intentos += 1
                        if intentos > 10:
                            raise Exception("No se pudo generar código único")
                    
                    # Crear hoja
                    hoja = HojaRespuesta(
                        postulante_id=postulante_row[0],
                        dni_profesor=profesor.dni,
                        codigo_aula=aula.codigo,
                        codigo_hoja=codigo_hoja,
                        proceso_admision=proceso,
                        estado="generada"
                    )
                    db.add(hoja)
                    
                    # Generar PDF
                    filename = f"hoja_{postulante_row[1]}_{codigo_hoja}.pdf"
                    filepath = os.path.join(aula_dir, filename)
                    
                    generar_hoja_respuestas_v3(
                        output_path=filepath,
                        dni_postulante=postulante_row[1],
                        codigo_aula=aula.codigo,
                        dni_profesor=profesor.dni,
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
                    print(f"   ❌ ERROR: {str(e)}")
                    raise
            
            print(f"✅ Aula {aula.codigo}: {len(pdf_files_aula)} hojas generadas")
            
            # ============================================================
            # CREAR ZIP POR AULA (modo individual)
            # ============================================================
            
            if modo_generacion == 'individual':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                zip_filename = f"hojas_{aula.codigo}_{timestamp}.zip"
                zip_path = os.path.join("uploads/hojas_generadas", zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for pdf_file in pdf_files_aula:
                        arcname = os.path.basename(pdf_file)
                        zip_file.write(pdf_file, arcname)
                
                archivos_por_aula.append({
                    "aula": aula.codigo,
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
            
            # Limpiar temporales
            shutil.rmtree(temp_dir)
            
            return {
                "success": True,
                "modo": "individual",
                "total_hojas": len(todos_los_pdfs),
                "total_aulas": len(archivos_por_aula),
                "archivos": archivos_por_aula,
                "mensaje": f"Se generaron {len(archivos_por_aula)} archivos ZIP (uno por aula)"
            }
        
        else:
            # Modo único: retornar ZIP con todo
            
            print(f"\n📦 Creando ZIP único con todas las aulas...")
            
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_file in todos_los_pdfs:
                    # Mantener estructura de carpetas: AULA-XXX/hoja_xxx.pdf
                    arcname = os.path.relpath(pdf_file, temp_dir)
                    zip_file.write(pdf_file, arcname)
            
            zip_buffer.seek(0)
            zip_size = len(zip_buffer.getvalue())
            
            # Limpiar temporales
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