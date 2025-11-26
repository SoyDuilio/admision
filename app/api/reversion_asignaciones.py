"""
Sistema de Gestión y Reversión de Asignaciones
Agregar a app/api/generar_hojas_aula.py o crear app/api/gestion_asignaciones.py

ENDPOINTS:
1. Estado del proceso
2. Limpiar todo el proceso
3. Limpiar por aula específica
4. Regenerar solo hojas (mantener asignaciones)
5. Limpiar hojas de una aula específica
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Aula, Postulante, Profesor
from app.models.hoja_respuesta import HojaRespuesta
from app.models.log_anulacion import LogAnulacionHoja

router = APIRouter()


# ============================================================================
# 1. ESTADO DEL PROCESO
# ============================================================================

@router.get("/estado-proceso")
async def obtener_estado_proceso(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado actual del proceso de asignaciones.
    """
    
    try:
        print(f"\n{'='*70}")
        print(f"🔍 OBTENIENDO ESTADO DEL PROCESO: {proceso}")
        print(f"{'='*70}")
        
        # Total postulantes
        print("1. Consultando total de postulantes...")
        total_postulantes = db.query(Postulante).filter(
            Postulante.activo == True,
            Postulante.proceso_admision == proceso
        ).count()
        print(f"   ✅ Total: {total_postulantes}")
        
        # Postulantes asignados
        print("2. Consultando postulantes asignados...")
        query_asignados = text("""
            SELECT COUNT(DISTINCT ae.postulante_id)
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.proceso_admision = :proceso
        """)
        asignados = db.execute(query_asignados, {"proceso": proceso}).scalar() or 0
        print(f"   ✅ Asignados: {asignados}")
        
        # Hojas generadas
        print("3. Consultando hojas generadas...")
        hojas_generadas = db.query(HojaRespuesta).filter(
            HojaRespuesta.proceso_admision == proceso
        ).count()
        print(f"   ✅ Hojas: {hojas_generadas}")
        
        # Aulas usadas
        print("4. Consultando aulas usadas...")
        query_aulas = text("""
            SELECT 
                a.id,
                a.codigo,
                a.nombre,
                COUNT(ae.id) as cantidad_asignados,
                COUNT(DISTINCT ae.profesor_id) as profesores
            FROM aulas a
            INNER JOIN asignaciones_examen ae ON a.id = ae.aula_id
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.proceso_admision = :proceso
            GROUP BY a.id, a.codigo, a.nombre
            ORDER BY a.codigo
        """)
        aulas = db.execute(query_aulas, {"proceso": proceso}).fetchall()
        print(f"   ✅ Aulas: {len(aulas)}")
        
        aulas_detalle = [
            {
                "aula_id": row[0],
                "codigo": row[1],
                "nombre": row[2],
                "asignados": row[3],
                "profesores": row[4]
            }
            for row in aulas
        ]
        
        # Logs de anulación
        print("5. Consultando logs...")
        logs_count = db.query(LogAnulacionHoja).join(
            HojaRespuesta,
            LogAnulacionHoja.hoja_respuesta_id == HojaRespuesta.id
        ).filter(
            HojaRespuesta.proceso_admision == proceso
        ).count()
        print(f"   ✅ Logs: {logs_count}")
        
        print(f"{'='*70}\n")
        
        return {
            "success": True,
            "proceso": proceso,
            "resumen": {
                "total_postulantes": total_postulantes,
                "postulantes_asignados": asignados,
                "postulantes_sin_asignar": total_postulantes - asignados,
                "hojas_generadas": hojas_generadas,
                "aulas_usadas": len(aulas_detalle),
                "logs_anulacion": logs_count
            },
            "aulas": aulas_detalle,
            "puede_asignar": (total_postulantes - asignados) > 0,
            "tiene_datos": asignados > 0 or hojas_generadas > 0
        }
        
    except Exception as e:
        print(f"\n❌ ERROR EN ESTADO-PROCESO:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        
        import traceback
        print("\n📋 Traceback completo:")
        traceback.print_exc()
        print(f"\n{'='*70}\n")
        
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 2. LIMPIAR TODO EL PROCESO
# ============================================================================

@router.post("/limpiar-proceso-completo")
async def limpiar_proceso_completo(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Limpia TODAS las asignaciones y hojas del proceso.
    
    Body:
    {
        "proceso_admision": "2025-2",
        "confirmar": true,
        "modo_desarrollo": false  // Si true, no pide segunda confirmación
    }
    """
    
    try:
        proceso = data.get('proceso_admision', '2025-2')
        confirmar = data.get('confirmar', False)
        modo_dev = data.get('modo_desarrollo', False)
        
        if not confirmar:
            raise HTTPException(
                status_code=400,
                detail="Debe confirmar la operación"
            )
        
        print(f"\n{'='*70}")
        print(f"🗑️  LIMPIEZA COMPLETA DEL PROCESO {proceso}")
        print(f"{'='*70}")
        
        # Contar elementos
        count_asignaciones = db.execute(text("""
            SELECT COUNT(*) FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE p.proceso_admision = :proceso
        """), {"proceso": proceso}).scalar()
        
        count_hojas = db.execute(text("""
            SELECT COUNT(*) FROM hojas_respuestas
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso}).scalar()
        
        count_logs = db.execute(text("""
            SELECT COUNT(*) FROM log_anulacion_hojas lah
            INNER JOIN hojas_respuestas hr ON lah.hoja_respuesta_id = hr.id
            WHERE hr.proceso_admision = :proceso
        """), {"proceso": proceso}).scalar()
        
        print(f"📊 A eliminar:")
        print(f"   Asignaciones: {count_asignaciones}")
        print(f"   Hojas: {count_hojas}")
        print(f"   Logs: {count_logs}")
        
        if count_asignaciones == 0 and count_hojas == 0:
            return {
                "success": True,
                "message": "No hay datos para limpiar",
                "eliminados": {"asignaciones": 0, "hojas": 0, "logs": 0}
            }
        
        # Eliminar en orden
        db.execute(text("""
            DELETE FROM log_anulacion_hojas
            WHERE hoja_respuesta_id IN (
                SELECT id FROM hojas_respuestas
                WHERE proceso_admision = :proceso
            )
        """), {"proceso": proceso})
        
        db.execute(text("""
            DELETE FROM hojas_respuestas
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso})
        
        db.execute(text("""
            DELETE FROM asignaciones_examen
            WHERE postulante_id IN (
                SELECT id FROM postulantes
                WHERE proceso_admision = :proceso
            )
        """), {"proceso": proceso})
        
        db.commit()
        
        print(f"✅ Limpieza completada\n")
        
        return {
            "success": True,
            "message": "Proceso limpiado exitosamente",
            "eliminados": {
                "asignaciones": count_asignaciones,
                "hojas": count_hojas,
                "logs": count_logs
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 3. LIMPIAR POR AULA ESPECÍFICA
# ============================================================================

@router.post("/limpiar-aula")
async def limpiar_aula_especifica(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Limpia asignaciones y hojas de un aula específica.
    
    Body:
    {
        "aula_id": 1,
        "proceso_admision": "2025-2",
        "confirmar": true
    }
    """
    
    try:
        aula_id = data.get('aula_id')
        proceso = data.get('proceso_admision', '2025-2')
        confirmar = data.get('confirmar', False)
        
        if not confirmar or not aula_id:
            raise HTTPException(status_code=400, detail="Faltan datos")
        
        # Obtener aula
        aula = db.query(Aula).filter_by(id=aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        print(f"\n🗑️  Limpiando aula {aula.codigo}...")
        
        # Obtener postulantes asignados a esta aula
        query_postulantes = text("""
            SELECT ae.postulante_id
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id
              AND p.proceso_admision = :proceso
        """)
        result = db.execute(query_postulantes, {
            "aula_id": aula_id,
            "proceso": proceso
        })
        postulante_ids = [row[0] for row in result.fetchall()]
        
        if not postulante_ids:
            return {
                "success": True,
                "message": f"Aula {aula.codigo} no tiene asignaciones",
                "eliminados": 0
            }
        
        # Eliminar logs
        db.execute(text("""
            DELETE FROM log_anulacion_hojas
            WHERE postulante_id = ANY(:ids)
        """), {"ids": postulante_ids})
        
        # Eliminar hojas
        db.execute(text("""
            DELETE FROM hojas_respuestas
            WHERE postulante_id = ANY(:ids)
              AND proceso_admision = :proceso
        """), {"ids": postulante_ids, "proceso": proceso})
        
        # Eliminar asignaciones
        db.execute(text("""
            DELETE FROM asignaciones_examen
            WHERE aula_id = :aula_id
              AND postulante_id = ANY(:ids)
        """), {"aula_id": aula_id, "ids": postulante_ids})
        
        db.commit()
        
        print(f"✅ Aula {aula.codigo} limpiada: {len(postulante_ids)} postulantes liberados\n")
        
        return {
            "success": True,
            "message": f"Aula {aula.codigo} limpiada exitosamente",
            "aula": aula.codigo,
            "eliminados": len(postulante_ids)
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 4. REGENERAR SOLO HOJAS (mantener asignaciones)
# ============================================================================

@router.post("/regenerar-hojas")
async def regenerar_solo_hojas(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Elimina hojas pero mantiene asignaciones.
    Útil para regenerar PDFs sin cambiar asignaciones.
    
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
            raise HTTPException(status_code=400, detail="Debe confirmar")
        
        print(f"\n🔄 Regenerando hojas del proceso {proceso}...")
        
        # Contar hojas
        count_hojas = db.query(HojaRespuesta).filter(
            HojaRespuesta.proceso_admision == proceso
        ).count()
        
        count_logs = db.execute(text("""
            SELECT COUNT(*) FROM log_anulacion_hojas lah
            INNER JOIN hojas_respuestas hr ON lah.hoja_respuesta_id = hr.id
            WHERE hr.proceso_admision = :proceso
        """), {"proceso": proceso}).scalar()
        
        print(f"   Hojas a eliminar: {count_hojas}")
        print(f"   Logs a eliminar: {count_logs}")
        
        # Eliminar logs
        db.execute(text("""
            DELETE FROM log_anulacion_hojas
            WHERE hoja_respuesta_id IN (
                SELECT id FROM hojas_respuestas
                WHERE proceso_admision = :proceso
            )
        """), {"proceso": proceso})
        
        # Eliminar hojas
        db.execute(text("""
            DELETE FROM hojas_respuestas
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso})
        
        db.commit()
        
        print(f"✅ Hojas eliminadas. Asignaciones mantenidas.\n")
        
        return {
            "success": True,
            "message": "Hojas eliminadas. Las asignaciones se mantienen intactas.",
            "eliminados": {
                "hojas": count_hojas,
                "logs": count_logs
            },
            "nota": "Ahora puede ejecutar la generación de hojas nuevamente"
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 5. LIMPIAR HOJAS DE UN AULA (mantener asignaciones)
# ============================================================================

@router.post("/limpiar-hojas-aula")
async def limpiar_hojas_aula(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Elimina solo las hojas de un aula específica.
    Mantiene las asignaciones intactas.
    
    Body:
    {
        "aula_id": 1,
        "proceso_admision": "2025-2",
        "confirmar": true
    }
    """
    
    try:
        aula_id = data.get('aula_id')
        proceso = data.get('proceso_admision', '2025-2')
        confirmar = data.get('confirmar', False)
        
        if not confirmar or not aula_id:
            raise HTTPException(status_code=400, detail="Faltan datos")
        
        aula = db.query(Aula).filter_by(id=aula_id).first()
        if not aula:
            raise HTTPException(status_code=404, detail="Aula no encontrada")
        
        print(f"\n🔄 Limpiando hojas del aula {aula.codigo}...")
        
        # Obtener hojas del aula
        count_hojas = db.query(HojaRespuesta).filter(
            HojaRespuesta.codigo_aula == aula.codigo,
            HojaRespuesta.proceso_admision == proceso
        ).count()
        
        # Eliminar logs
        db.execute(text("""
            DELETE FROM log_anulacion_hojas
            WHERE hoja_respuesta_id IN (
                SELECT id FROM hojas_respuestas
                WHERE codigo_aula = :codigo_aula
                  AND proceso_admision = :proceso
            )
        """), {"codigo_aula": aula.codigo, "proceso": proceso})
        
        # Eliminar hojas
        db.execute(text("""
            DELETE FROM hojas_respuestas
            WHERE codigo_aula = :codigo_aula
              AND proceso_admision = :proceso
        """), {"codigo_aula": aula.codigo, "proceso": proceso})
        
        db.commit()
        
        print(f"✅ Hojas del aula {aula.codigo} eliminadas: {count_hojas}\n")
        
        return {
            "success": True,
            "message": f"Hojas del aula {aula.codigo} eliminadas",
            "aula": aula.codigo,
            "eliminados": count_hojas,
            "nota": "Las asignaciones se mantienen intactas"
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))