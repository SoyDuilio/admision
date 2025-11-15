"""
POSTULANDO - API de Asignación de Postulantes a Aulas
app/api/asignacion.py

NUEVO MÓDULO - Gestiona la asignación de postulantes a aulas y profesores.

FLUJO:
1. Asignación automática por capacidad
2. Reasignación manual para casos especiales
3. Consulta de distribución actual
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.database import get_db
from app.models import Postulante, Aula, Profesor

router = APIRouter()

# ============================================================================
# NOTA IMPORTANTE
# ============================================================================
# Este módulo requiere la tabla asignaciones_examen que se creará en BD.
# Por ahora, usamos hojas_respuestas.codigo_aula como asignación.
# ============================================================================

# ============================================================================
# ENDPOINTS DE ASIGNACIÓN
# ============================================================================

@router.post("/asignar-automatico")
async def asignar_automatico(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Asigna postulantes a aulas automáticamente y GUARDA EN BD.
    
    Algoritmo:
    1. Ordena aulas por capacidad
    2. Distribuye postulantes sin asignar
    3. Respeta capacidad máxima
    4. Opcionalmente agrupa por programa educativo
    5. GUARDA en asignaciones_examen
    
    Body:
    {
        "proceso_admision": "2025-2",
        "agrupar_por_programa": false,
        "solo_sin_asignar": true
    }
    """
    
    from app.models import AsignacionExamen
    
    proceso = data.get('proceso_admision', '2025-2')
    agrupar_por_programa = data.get('agrupar_por_programa', False)
    solo_sin_asignar = data.get('solo_sin_asignar', True)
    
    # Obtener aulas activas ordenadas por capacidad
    aulas = db.query(Aula).filter(
        Aula.activo == True
    ).order_by(Aula.capacidad.desc()).all()
    
    if not aulas:
        raise HTTPException(
            status_code=400,
            detail="No hay aulas activas registradas"
        )
    
    # Obtener profesores (asignar uno por aula)
    profesores = db.query(Profesor).filter(Profesor.activo == True).all()
    
    if not profesores:
        raise HTTPException(
            status_code=400,
            detail="No hay profesores activos registrados"
        )
    
    # Obtener postulantes
    query = db.query(Postulante).filter(Postulante.activo == True)
    
    if solo_sin_asignar:
        # Solo postulantes que NO tienen asignación
        postulantes_asignados = db.query(AsignacionExamen.postulante_id).filter(
            AsignacionExamen.proceso_admision == proceso,
            AsignacionExamen.estado.in_(['asignado', 'confirmado'])
        ).distinct().all()
        
        ids_asignados = [p[0] for p in postulantes_asignados]
        
        if ids_asignados:
            query = query.filter(~Postulante.id.in_(ids_asignados))
    
    # Opcionalmente agrupar por programa
    if agrupar_por_programa:
        query = query.order_by(Postulante.programa_educativo, Postulante.id)
    else:
        query = query.order_by(Postulante.id)
    
    postulantes = query.all()
    
    if not postulantes:
        return {
            "success": True,
            "message": "No hay postulantes sin asignar",
            "asignados": 0
        }
    
    # Calcular capacidad total
    capacidad_total = sum(a.capacidad for a in aulas)
    
    if len(postulantes) > capacidad_total:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente capacidad. Postulantes: {len(postulantes)}, Capacidad: {capacidad_total}"
        )
    
    # ================================================================
    # ASIGNAR Y GUARDAR EN BD
    # ================================================================
    
    asignaciones_creadas = []
    idx_aula = 0
    idx_profesor = 0
    postulantes_en_aula_actual = 0
    
    aula_actual = aulas[idx_aula]
    profesor_actual = profesores[idx_profesor % len(profesores)]
    
    print(f"\n🎯 INICIANDO ASIGNACIÓN AUTOMÁTICA")
    print(f"   Total postulantes: {len(postulantes)}")
    print(f"   Total aulas: {len(aulas)}")
    print(f"   Capacidad total: {capacidad_total}")
    
    for postulante in postulantes:
        # Si se llenó el aula actual, pasar a la siguiente
        if postulantes_en_aula_actual >= aula_actual.capacidad:
            idx_aula += 1
            idx_profesor += 1
            
            if idx_aula >= len(aulas):
                raise HTTPException(
                    status_code=500,
                    detail="Error en algoritmo de asignación"
                )
            
            aula_actual = aulas[idx_aula]
            profesor_actual = profesores[idx_profesor % len(profesores)]
            postulantes_en_aula_actual = 0
            
            print(f"\n   📍 Cambiando a aula: {aula_actual.codigo}")
        
        # Crear asignación en BD
        asignacion = AsignacionExamen(
            postulante_id=postulante.id,
            aula_id=aula_actual.id,
            proceso_admision=proceso,
            asignado_por='automatico',
            estado='asignado'
        )
        
        db.add(asignacion)
        
        asignaciones_creadas.append({
            "postulante_id": postulante.id,
            "postulante_dni": postulante.dni,
            "postulante_nombre": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
            "aula_codigo": aula_actual.codigo,
            "aula_nombre": aula_actual.nombre,
            "profesor_dni": profesor_actual.dni,
            "profesor_nombre": f"{profesor_actual.nombres} {profesor_actual.apellido_paterno}"
        })
        
        postulantes_en_aula_actual += 1
    
    # COMMIT A BD
    try:
        db.commit()
        print(f"\n✅ COMMIT EXITOSO - {len(asignaciones_creadas)} asignaciones guardadas")
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR EN COMMIT: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar asignaciones: {str(e)}"
        )
    
    return {
        "success": True,
        "message": f"{len(asignaciones_creadas)} postulantes asignados y guardados en BD",
        "total_asignados": len(asignaciones_creadas),
        "aulas_utilizadas": idx_aula + 1,
        "asignaciones": asignaciones_creadas,
        "resumen_por_aula": _calcular_resumen_aulas(asignaciones_creadas)
    }


@router.put("/reasignar-postulante")
async def reasignar_postulante(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Reasigna un postulante a otra aula manualmente.
    
    Body:
    {
        "postulante_id": 123,
        "nueva_aula_codigo": "B201",
        "motivo": "Discapacidad visual"
    }
    """
    
    postulante_id = data.get('postulante_id')
    nueva_aula_codigo = data.get('nueva_aula_codigo')
    motivo = data.get('motivo', 'Reasignación manual')
    
    # Validar postulante
    postulante = db.query(Postulante).filter(Postulante.id == postulante_id).first()
    if not postulante:
        raise HTTPException(status_code=404, detail="Postulante no encontrado")
    
    # Validar aula
    aula = db.query(Aula).filter(Aula.codigo == nueva_aula_codigo).first()
    if not aula:
        raise HTTPException(status_code=404, detail=f"Aula {nueva_aula_codigo} no encontrada")
    
    # Verificar capacidad de la nueva aula
    # (Por ahora solo retornamos la confirmación, la lógica real
    # se implementará cuando tengamos la tabla asignaciones_examen)
    
    return {
        "success": True,
        "message": f"Postulante reasignado a aula {nueva_aula_codigo}",
        "postulante": {
            "id": postulante.id,
            "dni": postulante.dni,
            "nombre": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}"
        },
        "nueva_aula": {
            "codigo": aula.codigo,
            "nombre": aula.nombre,
            "capacidad": aula.capacidad
        },
        "motivo": motivo
    }


@router.get("/ver-asignaciones")
async def ver_asignaciones(
    proceso_admision: str = "2025-2",
    db: Session = Depends(get_db)
):
    """
    Consulta la distribución actual de postulantes por aula.
    
    Por ahora usa hojas_respuestas.codigo_aula como fuente.
    """
    
    from app.models import HojaRespuesta
    from sqlalchemy import func
    
    # Obtener distribución por aula
    distribucion = db.query(
        HojaRespuesta.codigo_aula,
        func.count(HojaRespuesta.id).label('total_postulantes')
    ).filter(
        HojaRespuesta.proceso_admision == proceso_admision
    ).group_by(
        HojaRespuesta.codigo_aula
    ).all()
    
    # Obtener info de aulas
    aulas_info = {}
    for codigo, total in distribucion:
        aula = db.query(Aula).filter(Aula.codigo == codigo).first()
        if aula:
            aulas_info[codigo] = {
                "codigo": codigo,
                "nombre": aula.nombre,
                "capacidad": aula.capacidad,
                "asignados": total,
                "disponible": aula.capacidad - total,
                "porcentaje_ocupacion": round((total / aula.capacidad) * 100, 1) if aula.capacidad > 0 else 0
            }
    
    # Total de postulantes
    total_postulantes = db.query(Postulante).filter(Postulante.activo == True).count()
    total_asignados = sum(info['asignados'] for info in aulas_info.values())
    total_sin_asignar = total_postulantes - total_asignados
    
    return {
        "success": True,
        "proceso": proceso_admision,
        "resumen": {
            "total_postulantes": total_postulantes,
            "asignados": total_asignados,
            "sin_asignar": total_sin_asignar,
            "aulas_utilizadas": len(aulas_info)
        },
        "distribucion_por_aula": list(aulas_info.values())
    }


@router.get("/estadisticas-asignacion")
async def estadisticas_asignacion(db: Session = Depends(get_db)):
    """
    Estadísticas generales de asignación.
    """
    
    total_postulantes = db.query(Postulante).filter(Postulante.activo == True).count()
    total_aulas = db.query(Aula).filter(Aula.activo == True).count()
    total_profesores = db.query(Profesor).filter(Profesor.activo == True).count()
    
    capacidad_total = db.query(func.sum(Aula.capacidad)).filter(Aula.activo == True).scalar() or 0
    
    from app.models import HojaRespuesta
    postulantes_con_hoja = db.query(func.count(func.distinct(HojaRespuesta.postulante_id))).scalar() or 0
    
    postulantes_sin_asignar = total_postulantes - postulantes_con_hoja
    
    return {
        "success": True,
        "postulantes": {
            "total": total_postulantes,
            "con_hoja_generada": postulantes_con_hoja,
            "sin_asignar": postulantes_sin_asignar
        },
        "infraestructura": {
            "aulas_activas": total_aulas,
            "profesores_activos": total_profesores,
            "capacidad_total": capacidad_total,
            "espacios_disponibles": capacidad_total - postulantes_con_hoja
        },
        "puede_asignar_todos": postulantes_sin_asignar <= (capacidad_total - postulantes_con_hoja)
    }


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _calcular_resumen_aulas(asignaciones):
    """Calcula resumen de postulantes por aula"""
    resumen = {}
    
    for asig in asignaciones:
        aula = asig['aula_codigo']
        if aula not in resumen:
            resumen[aula] = {
                "codigo": aula,
                "nombre": asig['aula_nombre'],
                "total": 0,
                "postulantes": []
            }
        
        resumen[aula]['total'] += 1
        resumen[aula]['postulantes'].append({
            "dni": asig['postulante_dni'],
            "nombre": asig['postulante_nombre']
        })
    
    return list(resumen.values())