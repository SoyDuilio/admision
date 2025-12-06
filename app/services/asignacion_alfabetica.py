"""
Servicio de Asignación Alfabética por Capacidad Completa
app/services/asignacion_alfabetica.py

Llena cada aula hasta su capacidad máxima antes de pasar a la siguiente.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict
from collections import Counter


def asignar_alfabeticamente(
    db: Session,
    proceso_admision: str = "2025-2"
) -> Dict:
    """
    Asigna postulantes a aulas alfabéticamente llenando COMPLETAMENTE cada aula.
    
    Algoritmo:
    1. Ordena postulantes alfabéticamente
    2. Ordena aulas por código
    3. Llena COMPLETAMENTE cada aula hasta su capacidad
    4. Asigna profesor evitando apellidos coincidentes
    5. Asigna número de orden correlativo (1, 2, 3...)
    
    Returns:
        {
            "success": bool,
            "total_asignados": int,
            "aulas_utilizadas": int,
            "detalle": [...]
        }
    """
    
    print(f"\n{'='*70}")
    print(f"🔤 ASIGNACIÓN ALFABÉTICA - LLENADO COMPLETO")
    print(f"Proceso: {proceso_admision}")
    print(f"{'='*70}")
    
    # ========================================================================
    # 1. OBTENER POSTULANTES SIN ASIGNAR (ORDENADOS ALFABÉTICAMENTE)
    # ========================================================================
    
    query_postulantes = text("""
        SELECT 
            p.id,
            p.dni,
            p.nombres,
            p.apellido_paterno,
            p.apellido_materno,
            p.programa_educativo
        FROM postulantes p
        WHERE p.proceso_admision = :proceso
          AND p.activo = true
          AND NOT EXISTS (
              SELECT 1 FROM asignaciones_examen ae
              WHERE ae.postulante_id = p.id
                AND ae.proceso_admision = :proceso
          )
        ORDER BY 
            p.apellido_paterno,
            p.apellido_materno,
            p.nombres
    """)
    
    result = db.execute(query_postulantes, {"proceso": proceso_admision})
    postulantes = result.fetchall()
    
    if not postulantes:
        print("⚠️  No hay postulantes sin asignar")
        return {
            "success": True,
            "message": "No hay postulantes pendientes de asignación",
            "total_asignados": 0,
            "aulas_utilizadas": 0
        }
    
    print(f"✅ Postulantes sin asignar: {len(postulantes)}")
    
    # ========================================================================
    # 2. OBTENER AULAS ACTIVAS (ORDENADAS POR CÓDIGO)
    # ========================================================================
    
    query_aulas = text("""
        SELECT id, codigo, capacidad, nombre
        FROM aulas
        WHERE activo = true
        ORDER BY codigo
    """)
    
    result_aulas = db.execute(query_aulas)
    aulas = result_aulas.fetchall()
    
    if not aulas:
        raise Exception("No hay aulas activas registradas")
    
    print(f"✅ Aulas disponibles: {len(aulas)}")
    
    # ========================================================================
    # 3. OBTENER PROFESORES ACTIVOS
    # ========================================================================
    
    query_profesores = text("""
        SELECT id, dni, apellido_paterno, apellido_materno, nombres
        FROM profesores
        WHERE activo = true
        ORDER BY apellido_paterno, apellido_materno
    """)
    
    result_profesores = db.execute(query_profesores)
    profesores = result_profesores.fetchall()
    
    if not profesores:
        raise Exception("No hay profesores activos")
    
    print(f"✅ Profesores disponibles: {len(profesores)}")
    
    # ========================================================================
    # 4. VERIFICAR CAPACIDAD TOTAL
    # ========================================================================
    
    total_postulantes = len(postulantes)
    capacidad_total = sum(a.capacidad for a in aulas)
    
    if total_postulantes > capacidad_total:
        raise Exception(
            f"Capacidad insuficiente: {total_postulantes} postulantes "
            f"vs {capacidad_total} espacios disponibles"
        )
    
    # Calcular aulas mínimas necesarias
    aulas_minimas = 0
    capacidad_acumulada = 0
    for aula in aulas:
        aulas_minimas += 1
        capacidad_acumulada += aula.capacidad
        if capacidad_acumulada >= total_postulantes:
            break
    
    print(f"📊 Capacidad total: {capacidad_total}")
    print(f"📊 Aulas mínimas necesarias: {aulas_minimas}")
    
    if len(profesores) < aulas_minimas:
        print(f"⚠️  Advertencia: Solo hay {len(profesores)} profesores para {aulas_minimas} aulas")
        print(f"    Se asignará el mismo profesor a múltiples aulas si es necesario")
    
    print(f"{'='*70}\n")
    
    # ========================================================================
    # 5. ASIGNAR PROFESOR ÓPTIMO POR AULA (evitando apellidos coincidentes)
    # ========================================================================
    
    def seleccionar_profesor_para_aula(postulantes_aula, profesores_disponibles):
        """
        Selecciona el mejor profesor para un aula.
        Prioriza profesores SIN apellidos coincidentes con postulantes.
        """
        apellidos_postulantes = set(p.apellido_paterno.upper() for p in postulantes_aula)
        
        # Intentar encontrar profesor sin apellido coincidente
        for profesor in profesores_disponibles:
            apellido_profesor = profesor.apellido_paterno.upper()
            if apellido_profesor not in apellidos_postulantes:
                return profesor
        
        # Si todos coinciden, devolver el primero
        return profesores_disponibles[0] if profesores_disponibles else None
    
    # ========================================================================
    # 6. ASIGNAR POSTULANTES AULA POR AULA (LLENADO COMPLETO)
    # ========================================================================
    
    print(f"🏫 ASIGNANDO POR AULA (llenado completo)\n")
    
    asignaciones = []
    idx_postulante = 0
    aulas_utilizadas = 0
    idx_profesor_rotativo = 0
    
    for aula in aulas:
        
        if idx_postulante >= total_postulantes:
            break
        
        aulas_utilizadas += 1
        
        # Determinar cuántos postulantes asignar a esta aula
        postulantes_para_esta_aula = min(
            aula.capacidad,
            total_postulantes - idx_postulante
        )
        
        # Extraer postulantes para esta aula
        postulantes_aula = postulantes[idx_postulante:idx_postulante + postulantes_para_esta_aula]
        
        # Seleccionar profesor óptimo
        profesor = seleccionar_profesor_para_aula(postulantes_aula, profesores)
        
        if not profesor:
            # Fallback: usar rotación simple
            profesor = profesores[idx_profesor_rotativo % len(profesores)]
            idx_profesor_rotativo += 1
        
        print(f"{'='*70}")
        print(f"📦 AULA {aulas_utilizadas}/{aulas_minimas}: {aula.codigo}")
        print(f"   Capacidad: {aula.capacidad}")
        print(f"   Asignados: {postulantes_para_esta_aula}")
        print(f"   Profesor: {profesor.apellido_paterno} {profesor.apellido_materno}, {profesor.nombres}")
        print(f"{'='*70}")
        
        # Asignar cada postulante con su orden
        for orden, postulante in enumerate(postulantes_aula, start=1):
            
            insert_query = text("""
                INSERT INTO asignaciones_examen (
                    postulante_id,
                    aula_id,
                    profesor_id,
                    proceso_admision,
                    orden_alfabetico,
                    asignado_por,
                    estado,
                    fecha_asignacion
                ) VALUES (
                    :postulante_id,
                    :aula_id,
                    :profesor_id,
                    :proceso,
                    :orden,
                    'automatico_alfabetico',
                    'confirmado',
                    NOW()
                )
            """)
            
            db.execute(insert_query, {
                "postulante_id": postulante.id,
                "aula_id": aula.id,
                "profesor_id": profesor.id,
                "proceso": proceso_admision,
                "orden": orden
            })
            
            asignaciones.append({
                "postulante_id": postulante.id,
                "dni": postulante.dni,
                "nombre": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "aula_codigo": aula.codigo,
                "orden": orden,
                "profesor": f"{profesor.apellido_paterno} {profesor.apellido_materno}"
            })
            
            # Progreso detallado cada 10
            if orden % 10 == 0 or orden == postulantes_para_esta_aula:
                print(f"   ✓ {orden:2d}. {postulante.apellido_paterno:15s} {postulante.apellido_materno:15s}, {postulante.nombres[:20]:20s}")
        
        idx_postulante += postulantes_para_esta_aula
        print()
    
    # ========================================================================
    # 7. COMMIT
    # ========================================================================
    
    db.commit()
    
    print(f"\n{'='*70}")
    print(f"✅ ASIGNACIÓN COMPLETADA")
    print(f"{'='*70}")
    print(f"Total asignados: {len(asignaciones)}")
    print(f"Aulas utilizadas: {aulas_utilizadas}")
    print(f"{'='*70}\n")
    
    # ========================================================================
    # 8. RESUMEN POR AULA
    # ========================================================================
    
    resumen_por_aula = {}
    for asig in asignaciones:
        aula = asig["aula_codigo"]
        if aula not in resumen_por_aula:
            resumen_por_aula[aula] = {
                "codigo": aula,
                "total": 0,
                "profesor": asig["profesor"],
                "primer_postulante": asig["nombre"],
                "ultimo_postulante": None
            }
        
        resumen_por_aula[aula]["total"] += 1
        resumen_por_aula[aula]["ultimo_postulante"] = asig["nombre"]
    
    return {
        "success": True,
        "total_asignados": len(asignaciones),
        "aulas_utilizadas": aulas_utilizadas,
        "resumen_por_aula": list(resumen_por_aula.values()),
        "mensaje": f"{len(asignaciones)} postulantes asignados en {aulas_utilizadas} aulas (llenado completo)"
    }