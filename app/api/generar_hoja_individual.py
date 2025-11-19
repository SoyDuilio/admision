"""
API para Generación Individual de Hojas
app/api/generar_hoja_individual.py

Sistema completo con trazabilidad y auditoría
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import random
import string

from app.database import get_db

router = APIRouter()


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class GenerarHojaIndividualRequest(BaseModel):
    postulante_id: int
    motivo: str
    solicitado_por: str
    entrego_anterior: bool = False
    observaciones: str = None


# ============================================================================
# ENDPOINT: BUSCAR POSTULANTE
# ============================================================================

@router.get("/buscar-postulante")
async def buscar_postulante(
    tipo: str = Query(..., description="dni o codigo"),
    valor: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Busca un postulante por DNI o código de hoja.
    """
    
    try:
        if tipo == "dni":
            # Buscar por DNI
            query = text("""
                SELECT 
                    p.id,
                    p.dni,
                    p.nombres,
                    p.apellido_paterno,
                    p.apellido_materno,
                    p.programa_educativo,
                    p.codigo_unico,
                    a.codigo as aula_codigo,
                    a.nombre as aula_nombre
                FROM postulantes p
                LEFT JOIN asignaciones_examen ae ON p.id = ae.postulante_id
                LEFT JOIN aulas a ON ae.aula_id = a.id
                WHERE p.dni = :valor
                  AND p.activo = true
                LIMIT 1
            """)
            
        else:  # tipo == "codigo"
            # Buscar por código de hoja
            query = text("""
                SELECT 
                    p.id,
                    p.dni,
                    p.nombres,
                    p.apellido_paterno,
                    p.apellido_materno,
                    p.programa_educativo,
                    p.codigo_unico,
                    a.codigo as aula_codigo,
                    a.nombre as aula_nombre
                FROM hojas_respuestas hr
                INNER JOIN postulantes p ON hr.postulante_id = p.id
                LEFT JOIN asignaciones_examen ae ON p.id = ae.postulante_id
                LEFT JOIN aulas a ON ae.aula_id = a.id
                WHERE hr.codigo_hoja = :valor
                  AND p.activo = true
                LIMIT 1
            """)
        
        result = db.execute(query, {"valor": valor})
        row = result.fetchone()
        
        if not row:
            return {
                "success": False,
                "message": f"No se encontró postulante con {tipo}: {valor}"
            }
        
        # Buscar hoja anterior
        query_hoja = text("""
            SELECT 
                codigo_hoja,
                estado,
                fecha_captura,
                observaciones
            FROM hojas_respuestas
            WHERE postulante_id = :postulante_id
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result_hoja = db.execute(query_hoja, {"postulante_id": row.id})
        hoja_row = result_hoja.fetchone()
        
        hoja_anterior = None
        if hoja_row:
            hoja_anterior = {
                "codigo": hoja_row.codigo_hoja,
                "estado": hoja_row.estado,
                "fecha": hoja_row.fecha_captura.strftime("%Y-%m-%d %H:%M") if hoja_row.fecha_captura else "N/A",
                "observaciones": hoja_row.observaciones
            }
        
        return {
            "success": True,
            "postulante": {
                "id": row.id,
                "dni": row.dni,
                "nombres": row.nombres,
                "nombre_completo": f"{row.apellido_paterno} {row.apellido_materno}, {row.nombres}",
                "programa": row.programa_educativo,
                "codigo_unico": row.codigo_unico,
                "aula": f"{row.aula_codigo} - {row.aula_nombre}" if row.aula_codigo else "Sin asignar",
                "hoja_anterior": hoja_anterior
            }
        }
        
    except Exception as e:
        print(f"Error en buscar_postulante: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": str(e)
        }


# ============================================================================
# ENDPOINT: GENERAR HOJA INDIVIDUAL
# ============================================================================

@router.post("/generar-hoja-individual")
async def generar_hoja_individual(
    request: GenerarHojaIndividualRequest,
    db: Session = Depends(get_db)
):
    """
    Genera una nueva hoja individual con trazabilidad completa.
    """
    
    try:
        # 1. Verificar que el postulante existe
        query_postulante = text("""
            SELECT id, dni, nombres, apellido_paterno, proceso_admision
            FROM postulantes
            WHERE id = :postulante_id AND activo = true
        """)
        
        result = db.execute(query_postulante, {"postulante_id": request.postulante_id})
        postulante = result.fetchone()
        
        if not postulante:
            raise HTTPException(status_code=404, detail="Postulante no encontrado")
        
        # 2. Generar código único de hoja
        nuevo_codigo = generar_codigo_hoja()
        
        # Verificar que no exista
        while verificar_codigo_existe(db, nuevo_codigo):
            nuevo_codigo = generar_codigo_hoja()
        
        # 3. Marcar hoja anterior como ANULADA (si existe)
        query_anular = text("""
            UPDATE hojas_respuestas
            SET estado = 'anulada',
                observaciones = CONCAT(
                    COALESCE(observaciones, ''), 
                    ' | ANULADA: ', :fecha, 
                    ' - Motivo: ', :motivo,
                    ' - Solicitado por: ', :solicitado_por
                )
            WHERE postulante_id = :postulante_id
              AND estado != 'anulada'
        """)
        
        db.execute(query_anular, {
            "postulante_id": request.postulante_id,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "motivo": request.motivo,
            "solicitado_por": request.solicitado_por
        })
        
        # 4. Crear nueva hoja
        query_insert = text("""
            INSERT INTO hojas_respuestas (
                postulante_id,
                codigo_hoja,
                proceso_admision,
                estado,
                observaciones,
                fecha_captura,
                created_at
            ) VALUES (
                :postulante_id,
                :codigo_hoja,
                :proceso_admision,
                'generada',
                :observaciones,
                :fecha,
                :fecha
            )
            RETURNING id
        """)
        
        observaciones_completas = f"""
HOJA INDIVIDUAL GENERADA
Motivo: {request.motivo}
Solicitado por: {request.solicitado_por}
Entregó hoja anterior: {'Sí' if request.entrego_anterior else 'No'}
{f'Observaciones: {request.observaciones}' if request.observaciones else ''}
        """.strip()
        
        result_insert = db.execute(query_insert, {
            "postulante_id": request.postulante_id,
            "codigo_hoja": nuevo_codigo,
            "proceso_admision": postulante.proceso_admision,
            "observaciones": observaciones_completas,
            "fecha": datetime.now()
        })
        
        nueva_hoja_id = result_insert.fetchone()[0]
        
        # 5. Registrar en log de auditoría (crear tabla si no existe)
        crear_tabla_auditoria(db)
        
        query_log = text("""
            INSERT INTO log_generacion_hojas (
                hoja_respuesta_id,
                postulante_id,
                tipo_generacion,
                motivo,
                solicitado_por,
                entrego_anterior,
                observaciones,
                fecha_generacion
            ) VALUES (
                :hoja_id,
                :postulante_id,
                'individual',
                :motivo,
                :solicitado_por,
                :entrego_anterior,
                :observaciones,
                :fecha
            )
        """)
        
        db.execute(query_log, {
            "hoja_id": nueva_hoja_id,
            "postulante_id": request.postulante_id,
            "motivo": request.motivo,
            "solicitado_por": request.solicitado_por,
            "entrego_anterior": request.entrego_anterior,
            "observaciones": request.observaciones,
            "fecha": datetime.now()
        })
        
        # 6. Commit
        db.commit()
        
        return {
            "success": True,
            "codigo_hoja": nuevo_codigo,
            "hoja_id": nueva_hoja_id,
            "postulante": {
                "dni": postulante.dni,
                "nombre": f"{postulante.apellido_paterno}, {postulante.nombres}"
            },
            "message": "Hoja generada exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error en generar_hoja_individual: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT: VERIFICAR REGENERACIÓN DE AULA
# ============================================================================

@router.get("/verificar-hojas-aula/{aula_id}")
async def verificar_hojas_aula(
    aula_id: int,
    db: Session = Depends(get_db)
):
    """
    Verifica si ya se generaron hojas para un aula.
    """
    
    try:
        query = text("""
            SELECT 
                COUNT(*) as total_hojas,
                MIN(hr.created_at) as primera_generacion,
                MAX(hr.created_at) as ultima_generacion
            FROM hojas_respuestas hr
            INNER JOIN asignaciones_examen ae ON hr.postulante_id = ae.postulante_id
            WHERE ae.aula_id = :aula_id
              AND hr.estado != 'anulada'
        """)
        
        result = db.execute(query, {"aula_id": aula_id})
        row = result.fetchone()
        
        if row.total_hojas > 0:
            return {
                "success": True,
                "hojas_generadas": True,
                "total_hojas": row.total_hojas,
                "primera_generacion": row.primera_generacion.strftime("%Y-%m-%d %H:%M:%S") if row.primera_generacion else None,
                "ultima_generacion": row.ultima_generacion.strftime("%Y-%m-%d %H:%M:%S") if row.ultima_generacion else None,
                "mensaje": f"Se generaron {row.total_hojas} hojas el {row.primera_generacion.strftime('%d/%m/%Y a las %H:%M')}"
            }
        else:
            return {
                "success": True,
                "hojas_generadas": False,
                "mensaje": "No se han generado hojas para esta aula"
            }
            
    except Exception as e:
        print(f"Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def generar_codigo_hoja() -> str:
    """
    Genera un código único de 9 caracteres.
    Formato: ABC12345D
    """
    letras1 = ''.join(random.choices(string.ascii_uppercase, k=3))
    numeros = ''.join(random.choices(string.digits, k=5))
    letra2 = random.choice(string.ascii_uppercase)
    return f"{letras1}{numeros}{letra2}"


def verificar_codigo_existe(db: Session, codigo: str) -> bool:
    """
    Verifica si un código de hoja ya existe.
    """
    query = text("SELECT COUNT(*) FROM hojas_respuestas WHERE codigo_hoja = :codigo")
    result = db.execute(query, {"codigo": codigo})
    count = result.scalar()
    return count > 0


def crear_tabla_auditoria(db: Session):
    """
    Crea la tabla de log de auditoría si no existe.
    """
    query = text("""
        CREATE TABLE IF NOT EXISTS log_generacion_hojas (
            id SERIAL PRIMARY KEY,
            hoja_respuesta_id INTEGER,
            postulante_id INTEGER,
            tipo_generacion VARCHAR(20),
            motivo TEXT,
            solicitado_por VARCHAR(200),
            entrego_anterior BOOLEAN DEFAULT FALSE,
            observaciones TEXT,
            fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (hoja_respuesta_id) REFERENCES hojas_respuestas(id),
            FOREIGN KEY (postulante_id) REFERENCES postulantes(id)
        )
    """)
    
    try:
        db.execute(query)
        db.commit()
    except:
        db.rollback()
        # Ya existe, no pasa nada


# ============================================================================
# ENDPOINT: DESCARGAR HOJA (placeholder)
# ============================================================================

@router.get("/descargar-hoja/{codigo_hoja}")
async def descargar_hoja(
    codigo_hoja: str,
    db: Session = Depends(get_db)
):
    """
    Descarga/genera el PDF de una hoja específica.
    """
    
    # TODO: Implementar generación de PDF
    # Por ahora retorna los datos
    
    query = text("""
        SELECT 
            hr.codigo_hoja,
            p.dni,
            p.nombres,
            p.apellido_paterno,
            p.apellido_materno,
            p.programa_educativo,
            a.codigo as aula_codigo
        FROM hojas_respuestas hr
        INNER JOIN postulantes p ON hr.postulante_id = p.id
        LEFT JOIN asignaciones_examen ae ON p.id = ae.postulante_id
        LEFT JOIN aulas a ON ae.aula_id = a.id
        WHERE hr.codigo_hoja = :codigo
    """)
    
    result = db.execute(query, {"codigo": codigo_hoja})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Hoja no encontrada")
    
    return {
        "success": True,
        "mensaje": "Generación de PDF pendiente de implementar",
        "datos": {
            "codigo": row.codigo_hoja,
            "dni": row.dni,
            "nombre": f"{row.apellido_paterno} {row.apellido_materno}, {row.nombres}",
            "programa": row.programa_educativo,
            "aula": row.aula_codigo
        }
    }


# ============================================================================
# ENDPOINT: REGENERAR HOJAS POR AULA
# ============================================================================

@router.post("/regenerar-hojas-aula/{aula_id}")
async def regenerar_hojas_aula(
    aula_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Regenera todas las hojas de un aula.
    Anula las anteriores y crea nuevas.
    """
    
    try:
        # 1. Obtener postulantes del aula
        query_postulantes = text("""
            SELECT p.id, p.dni, p.nombres, p.apellido_paterno
            FROM asignaciones_examen ae
            INNER JOIN postulantes p ON ae.postulante_id = p.id
            WHERE ae.aula_id = :aula_id
              AND p.activo = true
        """)
        
        result = db.execute(query_postulantes, {"aula_id": aula_id})
        postulantes = result.fetchall()
        
        if not postulantes:
            raise HTTPException(status_code=400, detail="No hay postulantes en esta aula")
        
        # 2. Anular hojas anteriores
        query_anular = text("""
            UPDATE hojas_respuestas hr
            SET estado = 'anulada',
                observaciones = CONCAT(
                    COALESCE(observaciones, ''),
                    ' | ANULADA POR REGENERACIÓN: ', :fecha,
                    ' - Motivo: ', :motivo,
                    ' - Autorizado por: ', :autorizado_por, ' (', :cargo, ')'
                )
            WHERE hr.postulante_id IN (
                SELECT ae.postulante_id 
                FROM asignaciones_examen ae 
                WHERE ae.aula_id = :aula_id
            )
            AND hr.estado != 'anulada'
        """)
        
        db.execute(query_anular, {
            "aula_id": aula_id,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "motivo": request.get("motivo"),
            "autorizado_por": request.get("autorizado_por"),
            "cargo": request.get("cargo")
        })
        
        # 3. Generar nuevas hojas
        hojas_generadas = []
        
        for postulante in postulantes:
            # Generar código único
            nuevo_codigo = generar_codigo_hoja()
            while verificar_codigo_existe(db, nuevo_codigo):
                nuevo_codigo = generar_codigo_hoja()
            
            # Insertar nueva hoja
            query_insert = text("""
                INSERT INTO hojas_respuestas (
                    postulante_id,
                    codigo_hoja,
                    proceso_admision,
                    estado,
                    observaciones,
                    created_at
                ) VALUES (
                    :postulante_id,
                    :codigo_hoja,
                    '2025-2',
                    'generada',
                    :observaciones,
                    :fecha
                )
            """)
            
            observaciones = f"""
REGENERACIÓN DE AULA
Motivo: {request.get('motivo')}
Autorizado por: {request.get('autorizado_por')} ({request.get('cargo')})
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            db.execute(query_insert, {
                "postulante_id": postulante.id,
                "codigo_hoja": nuevo_codigo,
                "observaciones": observaciones,
                "fecha": datetime.now()
            })
            
            hojas_generadas.append({
                "dni": postulante.dni,
                "codigo": nuevo_codigo
            })
        
        # 4. Commit
        db.commit()
        
        return {
            "success": True,
            "total_hojas": len(hojas_generadas),
            "hojas": hojas_generadas,
            "message": "Hojas regeneradas exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))