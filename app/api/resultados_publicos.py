"""
API de Resultados Públicos
Rutas para profesores/directivos y estudiantes
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime
import pytz

from app.database import get_db

router = APIRouter()


@router.get("/resultados/admin", response_class=HTMLResponse)
async def resultados_admin(
    request: Request,
    proceso: str = Query("2025-2")
):
    """
    Panel de resultados para profesores y directivos.
    Requiere login.
    """
    
    # Verificar login (temporal: permitir acceso sin login para testing)
    # if not current_user:
    #     return RedirectResponse("/admin/login?redirect=/resultados/admin")
    
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    
    return templates.TemplateResponse("public/resultados_admin.html", {
        "request": request,
        "proceso": proceso,
        "usuario": None
    })


@router.get("/api/estado-proceso")
async def obtener_estado_proceso(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado actual del proceso.
    
    Returns:
        {
            "estado": "captura" | "gabarito" | "evaluacion" | "publicado",
            "publicado": false,
            "hora_publicacion": "2024-12-06T10:30:00",
            "countdown_segundos": 3600
        }
    """
    
    try:
        query = text("""
            SELECT 
                estado,
                publicado,
                hora_publicacion_programada,
                fecha_publicacion
            FROM configuracion_proceso
            WHERE proceso_admision = :proceso
        """)
        
        result = db.execute(query, {"proceso": proceso}).fetchone()
        
        if not result:
            # Crear configuración por defecto
            query_insert = text("""
                INSERT INTO configuracion_proceso (proceso_admision, estado)
                VALUES (:proceso, 'captura')
                RETURNING estado, publicado, hora_publicacion_programada
            """)
            result = db.execute(query_insert, {"proceso": proceso}).fetchone()
            db.commit()
        
        # Calcular countdown si hay hora programada
        countdown_segundos = None
        if result.hora_publicacion_programada and not result.publicado:
            peru_tz = pytz.timezone('America/Lima')
            ahora = datetime.now(peru_tz)
            hora_pub = result.hora_publicacion_programada.replace(tzinfo=peru_tz)
            diferencia = (hora_pub - ahora).total_seconds()
            countdown_segundos = int(diferencia) if diferencia > 0 else 0
        
        return {
            "success": True,
            "proceso": proceso,
            "estado": result.estado,
            "publicado": result.publicado or False,
            "hora_publicacion": result.hora_publicacion_programada.isoformat() if result.hora_publicacion_programada else None,
            "countdown_segundos": countdown_segundos,
            "fecha_publicacion_real": result.fecha_publicacion.isoformat() if result.fecha_publicacion else None
        }
        
    except Exception as e:
        print(f"Error obteniendo estado: {str(e)}")
        return {
            "success": False,
            "estado": "captura",
            "publicado": False
        }


@router.get("/api/estadisticas-examen")
async def obtener_estadisticas(
    proceso: str = Query("2025-2"),
    db: Session = Depends(get_db)
):
    """
    Estadísticas generales del examen.
    """
    
    try:
        # Total hojas capturadas
        query_capturadas = text("""
            SELECT COUNT(*) 
            FROM hojas_respuestas
            WHERE proceso_admision = :proceso
              AND estado IN ('procesada', 'calificada')
        """)
        total_capturadas = db.execute(query_capturadas, {"proceso": proceso}).scalar() or 0
        
        # Total con DNI validado
        query_validadas = text("""
            SELECT COUNT(*)
            FROM validaciones_dni vd
            INNER JOIN hojas_respuestas hr ON vd.hoja_respuesta_id = hr.id
            WHERE hr.proceso_admision = :proceso
              AND vd.estado = 'validado'
        """)
        total_validadas = db.execute(query_validadas, {"proceso": proceso}).scalar() or 0
        
        # Total evaluadas
        query_evaluadas = text("""
            SELECT COUNT(*)
            FROM resultados_examen
            WHERE proceso_admision = :proceso
        """)
        total_evaluadas = db.execute(query_evaluadas, {"proceso": proceso}).scalar() or 0
        
        # Promedio general
        query_promedio = text("""
            SELECT AVG(nota_con_bono)
            FROM resultados_examen
            WHERE proceso_admision = :proceso
        """)
        promedio = db.execute(query_promedio, {"proceso": proceso}).scalar() or 0
        
        # Total aprobados (nota >= 55)
        query_aprobados = text("""
            SELECT COUNT(*)
            FROM resultados_examen
            WHERE proceso_admision = :proceso
              AND nota_con_bono >= 55
        """)
        total_aprobados = db.execute(query_aprobados, {"proceso": proceso}).scalar() or 0
        
        # Distribución por programa
        query_programas = text("""
            SELECT 
                programa_educativo,
                COUNT(*) as total,
                AVG(nota_con_bono) as promedio,
                MAX(nota_con_bono) as nota_maxima,
                MIN(nota_con_bono) as nota_minima
            FROM resultados_examen
            WHERE proceso_admision = :proceso
            GROUP BY programa_educativo
            ORDER BY programa_educativo
        """)
        distribucion = db.execute(query_programas, {"proceso": proceso}).fetchall()
        
        programas_data = []
        for p in distribucion:
            programas_data.append({
                "programa": p.programa_educativo,
                "total": p.total,
                "promedio": float(p.promedio) if p.promedio else 0,
                "nota_maxima": float(p.nota_maxima) if p.nota_maxima else 0,
                "nota_minima": float(p.nota_minima) if p.nota_minima else 0
            })
        
        return {
            "success": True,
            "proceso": proceso,
            "total_hojas_capturadas": total_capturadas,
            "total_dni_validados": total_validadas,
            "total_evaluadas": total_evaluadas,
            "promedio_general": round(float(promedio), 2) if promedio else 0,
            "total_aprobados": total_aprobados,
            "tasa_aprobacion": round((total_aprobados / total_evaluadas * 100), 2) if total_evaluadas > 0 else 0,
            "distribucion_programas": programas_data
        }
        
    except Exception as e:
        print(f"Error en estadísticas: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/resultados-detallados")
async def obtener_resultados_detallados(
    proceso: str = Query("2025-2"),
    programa: str = Query(None),
    orden: str = Query("nota_desc"),  # nota_desc, nota_asc, alfabetico
    db: Session = Depends(get_db)
):
    """
    Lista completa de resultados con filtros.
    """
    
    try:
        # Construir query base
        where_clauses = ["r.proceso_admision = :proceso"]
        params = {"proceso": proceso}
        
        if programa:
            where_clauses.append("r.programa_educativo = :programa")
            params["programa"] = programa
        
        where_sql = " AND ".join(where_clauses)
        
        # Ordenamiento
        if orden == "nota_desc":
            order_sql = "r.nota_con_bono DESC"
        elif orden == "nota_asc":
            order_sql = "r.nota_con_bono ASC"
        else:  # alfabetico
            order_sql = "r.nombres_completos ASC"
        
        query = text(f"""
            SELECT 
                r.id,
                r.dni,
                r.nombres_completos,
                r.programa_educativo,
                r.nota_final,
                r.bono_aplicado,
                r.nota_con_bono,
                r.respuestas_correctas,
                r.respuestas_incorrectas,
                r.respuestas_vacias,
                r.posicion_general,
                r.posicion_programa,
                r.ingreso,
                r.motivo_ingreso,
                r.url_foto_hoja,
                r.fecha_calculo
            FROM resultados_examen r
            WHERE {where_sql}
            ORDER BY {order_sql}
        """)
        
        result = db.execute(query, params)
        resultados = result.fetchall()
        
        data = []
        for r in resultados:
            data.append({
                "id": r.id,
                "dni": r.dni,
                "nombres": r.nombres_completos,
                "programa": r.programa_educativo,
                "nota_final": float(r.nota_final) if r.nota_final else 0,
                "bono": float(r.bono_aplicado) if r.bono_aplicado else 0,
                "nota_con_bono": float(r.nota_con_bono) if r.nota_con_bono else 0,
                "correctas": r.respuestas_correctas or 0,
                "incorrectas": r.respuestas_incorrectas or 0,
                "vacias": r.respuestas_vacias or 0,
                "posicion_general": r.posicion_general,
                "posicion_programa": r.posicion_programa,
                "ingreso": r.ingreso or False,
                "motivo_ingreso": r.motivo_ingreso,
                "foto_hoja": r.url_foto_hoja,
                "fecha": r.fecha_calculo.isoformat() if r.fecha_calculo else None
            })
        
        return {
            "success": True,
            "total": len(data),
            "resultados": data
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))