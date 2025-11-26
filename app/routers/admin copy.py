"""
POSTULANDO - Router Administrativo
app/routers/admin.py

Endpoints para:
- Autenticación de administradores
- Dashboard y estadísticas
- Gestión de gabarito
- Calificación de hojas
- Ranking y resultados
- Publicación oficial
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timedelta
import json

from app.database import get_db
from app.services.calificacion import CalificacionService
from app.services.auth_admin import (
    verificar_sesion_admin,
    crear_sesion_admin,
    cerrar_sesion_admin,
    obtener_usuario_actual
)
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["Administración"])
templates = Jinja2Templates(directory="app/templates")

# Agregar filtros personalizados para Jinja2
def format_number(value):
    """Formatear número con separador de miles"""
    try:
        return f"{int(value):,}".replace(",", ",")
    except (ValueError, TypeError):
        return value or 0

def format_decimal(value, decimals=2):
    """Formatear decimal"""
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return value or 0

def format_percentage(value, decimals=1):
    """Formatear porcentaje"""
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return f"{value}%"

templates.env.filters['format_number'] = format_number
templates.env.filters['format_decimal'] = format_decimal
templates.env.filters['format_percentage'] = format_percentage


# ============================================================
# SCHEMAS
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    remember: bool = False


class GabaritoRequest(BaseModel):
    proceso: str
    respuestas: list  # [{numero_pregunta: 1, respuesta_correcta: "A"}, ...]


class CalificacionRequest(BaseModel):
    proceso: str


class PublicacionRequest(BaseModel):
    proceso: str
    mostrar_dni: bool = True
    mostrar_nota: bool = True
    permitir_consulta: bool = True
    generar_acta: bool = False
    notificar_email: bool = False
    cuando_publicar: str = "ahora"
    fecha_programada: Optional[str] = None
    autorizante_nombre: str
    autorizante_cargo: str
    password: str


# ============================================================
# AUTENTICACIÓN
# ============================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login"""
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "proceso_actual": obtener_proceso_actual()}
    )


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Procesar login"""
    # Verificar credenciales
    query = text("""
        SELECT id, username, nombres, apellidos, rol, cargo, foto_url, activo
        FROM usuarios_admin
        WHERE (username = :username OR email = :username)
        AND password_hash = crypt(:password, password_hash)
        AND activo = true
    """)
    
    result = db.execute(query, {
        "username": request.username,
        "password": request.password
    }).fetchone()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    
    # Crear sesión
    token = crear_sesion_admin(
        db=db,
        usuario_id=result.id,
        remember=request.remember
    )
    
    # Registrar acceso
    db.execute(text("""
        UPDATE usuarios_admin 
        SET ultimo_acceso = NOW() 
        WHERE id = :id
    """), {"id": result.id})
    db.commit()
    
    response = JSONResponse({
        "success": True,
        "redirect": "/admin",
        "usuario": {
            "id": result.id,
            "nombres": result.nombres,
            "rol": result.rol
        }
    })
    
    # Establecer cookie
    max_age = 30 * 24 * 60 * 60 if request.remember else 8 * 60 * 60
    response.set_cookie(
        key="admin_session",
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax"
    )
    
    return response


@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Cerrar sesión"""
    token = request.cookies.get("admin_session")
    if token:
        cerrar_sesion_admin(db, token)
    
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response


# ============================================================
# DASHBOARD
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Dashboard principal"""
    proceso = obtener_proceso_actual()
    
    # Obtener estadísticas generales
    stats = obtener_estadisticas_generales(db, proceso)
    
    # Verificar estado del proceso
    gabarito_info = verificar_gabarito(db, proceso)
    calificacion_info = verificar_calificacion(db, proceso)
    publicacion_info = verificar_publicacion(db, proceso)
    
    # Top 10 postulantes
    top_postulantes = obtener_top_postulantes(db, proceso, 10)
    
    # Estadísticas por programa
    programas_stats = obtener_stats_por_programa(db, proceso)
    
    # Actividad reciente
    actividad_reciente = obtener_actividad_reciente(db, proceso)
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "dashboard",
            "stats": stats,
            "gabarito_registrado": gabarito_info["existe"],
            "gabarito_fecha": gabarito_info.get("fecha"),
            "calificacion_ejecutada": calificacion_info["ejecutada"],
            "calificacion_fecha": calificacion_info.get("fecha"),
            "ranking_generado": calificacion_info["ejecutada"],
            "resultados_publicados": publicacion_info["publicado"],
            "publicacion_fecha": publicacion_info.get("fecha"),
            "top_postulantes": top_postulantes,
            "programas_stats": programas_stats,
            "actividad_reciente": actividad_reciente
        }
    )


# ============================================================
# GABARITO
# ============================================================

@router.get("/gabarito", response_class=HTMLResponse)
async def gabarito_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Página de gestión de gabarito"""
    proceso = obtener_proceso_actual()
    gabarito_info = verificar_gabarito(db, proceso)
    
    # Si existe, obtener las respuestas
    gabarito = []
    distribucion = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    
    if gabarito_info["existe"]:
        result = db.execute(text("""
            SELECT numero_pregunta, respuesta_correcta
            FROM clave_respuestas
            WHERE proceso_admision = :proceso
            ORDER BY numero_pregunta
        """), {"proceso": proceso}).fetchall()
        
        gabarito = [r.respuesta_correcta for r in result]
        
        for r in result:
            if r.respuesta_correcta in distribucion:
                distribucion[r.respuesta_correcta] += 1
    
    return templates.TemplateResponse(
        "admin/gabarito/gestionar.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "gabarito",
            "gabarito_existe": gabarito_info["existe"],
            "total_respuestas": gabarito_info.get("total", 0),
            "gabarito_fecha": gabarito_info.get("fecha"),
            "gabarito_usuario": gabarito_info.get("usuario"),
            "gabarito": gabarito,
            "dist_a": distribucion["A"],
            "dist_b": distribucion["B"],
            "dist_c": distribucion["C"],
            "dist_d": distribucion["D"],
            "dist_e": distribucion["E"]
        }
    )


@router.post("/api/gabarito/guardar")
async def guardar_gabarito(
    request: GabaritoRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Guardar gabarito (respuestas correctas)"""
    
    if len(request.respuestas) != 100:
        raise HTTPException(
            status_code=400,
            detail=f"Se requieren exactamente 100 respuestas. Recibidas: {len(request.respuestas)}"
        )
    
    # Validar que todas las respuestas sean válidas
    validas = {"A", "B", "C", "D", "E"}
    for r in request.respuestas:
        if r["respuesta_correcta"].upper() not in validas:
            raise HTTPException(
                status_code=400,
                detail=f"Respuesta inválida en pregunta {r['numero_pregunta']}: {r['respuesta_correcta']}"
            )
    
    # Eliminar gabarito anterior si existe
    db.execute(text("""
        DELETE FROM clave_respuestas WHERE proceso_admision = :proceso
    """), {"proceso": request.proceso})
    
    # Insertar nuevas respuestas
    for r in request.respuestas:
        db.execute(text("""
            INSERT INTO clave_respuestas (numero_pregunta, respuesta_correcta, proceso_admision, created_at)
            VALUES (:numero, :respuesta, :proceso, NOW())
        """), {
            "numero": r["numero_pregunta"],
            "respuesta": r["respuesta_correcta"].upper(),
            "proceso": request.proceso
        })
    
    # Registrar en auditoría
    db.execute(text("""
        INSERT INTO auditoria_proceso (
            proceso_admision, accion, usuario_id, detalles, created_at
        ) VALUES (
            :proceso, 'GABARITO_REGISTRADO', :usuario_id, :detalles, NOW()
        )
    """), {
        "proceso": request.proceso,
        "usuario_id": usuario["id"],
        "detalles": json.dumps({"total_respuestas": 100})
    })
    
    db.commit()
    
    return {"success": True, "message": "Gabarito guardado correctamente"}


# ============================================================
# CALIFICACIÓN
# ============================================================

@router.get("/calificacion", response_class=HTMLResponse)
async def calificacion_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Página de calificación"""
    proceso = obtener_proceso_actual()
    
    gabarito_info = verificar_gabarito(db, proceso)
    calificacion_info = verificar_calificacion(db, proceso)
    
    # Contar hojas
    hojas_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN estado IN ('PROCESADO', 'procesado') THEN 1 END) as procesadas,
            COUNT(CASE WHEN nota_final IS NOT NULL THEN 1 END) as calificadas
        FROM hojas_respuestas
        WHERE proceso_admision = :proceso
    """), {"proceso": proceso}).fetchone()
    
    # Distribución de notas si ya hay calificación
    distribucion = {}
    if calificacion_info["ejecutada"]:
        dist_result = db.execute(text("""
            SELECT * FROM vw_estadisticas_proceso WHERE proceso_admision = :proceso
        """), {"proceso": proceso}).fetchone()
        
        if dist_result:
            distribucion = {
                "90_100": dist_result.rango_90_100 or 0,
                "80_89": dist_result.rango_80_89 or 0,
                "70_79": dist_result.rango_70_79 or 0,
                "60_69": dist_result.rango_60_69 or 0,
                "50_59": dist_result.rango_50_59 or 0,
                "menos_50": dist_result.rango_menos_50 or 0
            }
    
    # Calcular porcentajes para las barras
    total = hojas_stats.calificadas or 1
    for key in distribucion:
        distribucion[f"{key}_pct"] = (distribucion.get(key, 0) / total) * 100
    
    return templates.TemplateResponse(
        "admin/calificacion/ejecutar.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "calificacion",
            "gabarito_ok": gabarito_info["existe"],
            "gabarito_fecha": gabarito_info.get("fecha"),
            "hojas_ok": hojas_stats.procesadas > 0,
            "total_hojas": hojas_stats.procesadas or 0,
            "hojas_pendientes": hojas_stats.total - hojas_stats.procesadas,
            "calificacion_lista": gabarito_info["existe"] and hojas_stats.procesadas > 0,
            "ya_calificado": calificacion_info["ejecutada"],
            "ultima_calificacion": calificacion_info.get("fecha"),
            **{f"dist_{k}": v for k, v in distribucion.items()}
        }
    )


@router.post("/api/calificacion/ejecutar")
async def ejecutar_calificacion(
    request: CalificacionRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Ejecutar proceso de calificación"""
    
    servicio = CalificacionService(db)
    
    try:
        resultado = servicio.calificar_todas_las_hojas(request.proceso)
        
        # Registrar en auditoría
        db.execute(text("""
            INSERT INTO auditoria_proceso (
                proceso_admision, accion, usuario_id, detalles, created_at
            ) VALUES (
                :proceso, 'CALIFICACION_EJECUTADA', :usuario_id, :detalles, NOW()
            )
        """), {
            "proceso": request.proceso,
            "usuario_id": usuario["id"],
            "detalles": json.dumps(resultado)
        })
        
        db.commit()
        
        return {
            "success": True,
            "total_hojas": resultado["total_hojas"],
            "tiempo": f"{resultado['tiempo_segundos']:.2f}s",
            "promedio_nota": resultado["promedio_nota"],
            "nota_maxima": resultado["nota_maxima"],
            "nota_minima": resultado["nota_minima"]
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# RANKING
# ============================================================

@router.get("/ranking", response_class=HTMLResponse)
async def ranking_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
    limit: str = "50"
):
    """Página de ranking"""
    proceso = obtener_proceso_actual()
    
    # Obtener ranking
    limit_num = None if limit == "all" else int(limit)
    
    query = """
        SELECT 
            ROW_NUMBER() OVER (ORDER BY nota_final DESC, respuestas_correctas_count DESC) as ranking,
            p.id as postulante_id,
            p.dni,
            p.codigo_unico,
            p.nombres,
            p.apellido_paterno,
            p.apellido_materno,
            p.programa_educativo,
            hr.id as hoja_id,
            hr.respuestas_correctas_count as respuestas_correctas,
            hr.nota_final
        FROM hojas_respuestas hr
        JOIN postulantes p ON p.id = hr.postulante_id
        WHERE hr.proceso_admision = :proceso
        AND hr.nota_final IS NOT NULL
        ORDER BY hr.nota_final DESC, hr.respuestas_correctas_count DESC
    """
    
    if limit_num:
        query += f" LIMIT {limit_num}"
    
    ranking = db.execute(text(query), {"proceso": proceso}).fetchall()
    
    # Top 3 para el podium
    top3 = ranking[:3] if len(ranking) >= 3 else ranking
    
    # Programas únicos para filtro
    programas = db.execute(text("""
        SELECT DISTINCT programa_educativo 
        FROM postulantes 
        WHERE proceso_admision = :proceso
        ORDER BY programa_educativo
    """), {"proceso": proceso}).fetchall()
    
    # Estadísticas
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            AVG(nota_final) as promedio,
            MAX(nota_final) as maxima,
            MIN(nota_final) as minima,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY nota_final) as mediana
        FROM hojas_respuestas
        WHERE proceso_admision = :proceso AND nota_final IS NOT NULL
    """), {"proceso": proceso}).fetchone()
    
    # Nota aprobatoria (puede venir de configuración)
    nota_aprobatoria = 50  # Por defecto
    
    return templates.TemplateResponse(
        "admin/resultados/ranking.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "ranking",
            "ranking": ranking,
            "top3": [{"nombre_completo": f"{r.apellido_paterno} {r.apellido_materno}, {r.nombres}",
                      "programa_educativo": r.programa_educativo,
                      "nota_final": r.nota_final} for r in top3],
            "programas": [p.programa_educativo for p in programas],
            "total_postulantes": stats.total or 0,
            "promedio": stats.promedio or 0,
            "nota_maxima": stats.maxima or 0,
            "nota_minima": stats.minima or 0,
            "mediana": stats.mediana or 0,
            "nota_aprobatoria": nota_aprobatoria
        }
    )


# ============================================================
# PUBLICACIÓN DE RESULTADOS
# ============================================================

@router.get("/resultados", response_class=HTMLResponse)
async def resultados_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Página de publicación de resultados"""
    proceso = obtener_proceso_actual()
    
    # Verificaciones
    gabarito_info = verificar_gabarito(db, proceso)
    calificacion_info = verificar_calificacion(db, proceso)
    publicacion_info = verificar_publicacion(db, proceso)
    
    # Estadísticas
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN nota_final IS NOT NULL THEN 1 END) as calificados,
            COUNT(CASE WHEN nota_final >= 50 THEN 1 END) as ingresantes,
            AVG(nota_final) as promedio
        FROM hojas_respuestas
        WHERE proceso_admision = :proceso
    """), {"proceso": proceso}).fetchone()
    
    # Hojas pendientes de revisión
    revision_pendiente = db.execute(text("""
        SELECT COUNT(*) as total
        FROM hojas_respuestas
        WHERE proceso_admision = :proceso
        AND (estado = 'REQUIERE_REVISION' OR observaciones IS NOT NULL)
    """), {"proceso": proceso}).fetchone()
    
    # Resumen por programa
    programas_resumen = db.execute(text("""
        SELECT 
            p.programa_educativo as nombre,
            COUNT(*) as total,
            COUNT(CASE WHEN hr.nota_final >= 50 THEN 1 END) as ingresantes,
            MIN(CASE WHEN hr.nota_final >= 50 THEN hr.nota_final END) as nota_minima,
            30 as vacantes  -- Esto debería venir de configuración
        FROM hojas_respuestas hr
        JOIN postulantes p ON p.id = hr.postulante_id
        WHERE hr.proceso_admision = :proceso
        AND hr.nota_final IS NOT NULL
        GROUP BY p.programa_educativo
        ORDER BY p.programa_educativo
    """), {"proceso": proceso}).fetchall()
    
    nota_corte = 50  # Configurable
    
    return templates.TemplateResponse(
        "admin/resultados/publicar.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "resultados",
            "gabarito_ok": gabarito_info["existe"],
            "calificacion_ok": calificacion_info["ejecutada"],
            "todas_calificadas": stats.calificados == stats.total,
            "hojas_calificadas": stats.calificados or 0,
            "total_hojas": stats.total or 0,
            "sin_revision_pendiente": (revision_pendiente.total or 0) == 0,
            "hojas_pendientes_revision": revision_pendiente.total or 0,
            "puede_publicar": gabarito_info["existe"] and calificacion_info["ejecutada"],
            "resultados_publicados": publicacion_info["publicado"],
            "fecha_publicacion": publicacion_info.get("fecha"),
            "publicado_por": publicacion_info.get("usuario"),
            "url_resultados": f"/resultados/{proceso}",
            "url_consulta": f"/consulta/{proceso}",
            "total_postulantes": stats.total or 0,
            "total_ingresantes": stats.ingresantes or 0,
            "total_no_ingresaron": (stats.total or 0) - (stats.ingresantes or 0),
            "promedio": stats.promedio or 0,
            "nota_corte": nota_corte,
            "programas_resumen": programas_resumen
        }
    )


@router.post("/api/resultados/publicar")
async def publicar_resultados(
    request: PublicacionRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Publicar resultados oficialmente"""
    
    # Verificar contraseña del autorizante
    check_password = db.execute(text("""
        SELECT id FROM usuarios_admin
        WHERE id = :id AND password_hash = crypt(:password, password_hash)
    """), {"id": usuario["id"], "password": request.password}).fetchone()
    
    if not check_password:
        raise HTTPException(status_code=401, detail="Contraseña de autorización incorrecta")
    
    # Verificar que el usuario tenga permisos para publicar
    if usuario["rol"] not in ["RECTOR", "DIRECTOR"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para publicar resultados")
    
    # Registrar publicación
    fecha_publicacion = datetime.now()
    if request.cuando_publicar == "programar" and request.fecha_programada:
        fecha_publicacion = datetime.fromisoformat(request.fecha_programada)
    
    db.execute(text("""
        INSERT INTO publicaciones_resultados (
            proceso_admision,
            fecha_publicacion,
            publicado_por_id,
            autorizante_nombre,
            autorizante_cargo,
            configuracion,
            estado,
            created_at
        ) VALUES (
            :proceso,
            :fecha,
            :usuario_id,
            :autorizante_nombre,
            :autorizante_cargo,
            :config,
            :estado,
            NOW()
        )
    """), {
        "proceso": request.proceso,
        "fecha": fecha_publicacion,
        "usuario_id": usuario["id"],
        "autorizante_nombre": request.autorizante_nombre,
        "autorizante_cargo": request.autorizante_cargo,
        "config": json.dumps({
            "mostrar_dni": request.mostrar_dni,
            "mostrar_nota": request.mostrar_nota,
            "permitir_consulta": request.permitir_consulta
        }),
        "estado": "PROGRAMADO" if request.cuando_publicar == "programar" else "PUBLICADO"
    })
    
    # Registrar en auditoría
    db.execute(text("""
        INSERT INTO auditoria_proceso (
            proceso_admision, accion, usuario_id, detalles, created_at
        ) VALUES (
            :proceso, 'RESULTADOS_PUBLICADOS', :usuario_id, :detalles, NOW()
        )
    """), {
        "proceso": request.proceso,
        "usuario_id": usuario["id"],
        "detalles": json.dumps({
            "autorizante": request.autorizante_nombre,
            "cargo": request.autorizante_cargo,
            "fecha": fecha_publicacion.isoformat()
        })
    })
    
    db.commit()
    
    return {"success": True, "message": "Resultados publicados correctamente"}


# ============================================================
# ESTADÍSTICAS
# ============================================================

@router.get("/estadisticas", response_class=HTMLResponse)
async def estadisticas_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Página de estadísticas detalladas"""
    proceso = obtener_proceso_actual()
    
    # Estadísticas generales
    stats_generales = db.execute(text("""
        SELECT * FROM vw_estadisticas_proceso WHERE proceso_admision = :proceso
    """), {"proceso": proceso}).fetchone()
    
    # Estadísticas por programa
    stats_programa = db.execute(text("""
        SELECT * FROM vw_ranking_por_programa WHERE proceso_admision = :proceso
    """), {"proceso": proceso}).fetchall()
    
    # Análisis de preguntas (más difíciles y más fáciles)
    preguntas_dificiles = db.execute(text("""
        SELECT * FROM vw_analisis_preguntas 
        WHERE proceso_admision = :proceso 
        ORDER BY porcentaje_acierto ASC 
        LIMIT 10
    """), {"proceso": proceso}).fetchall()
    
    preguntas_faciles = db.execute(text("""
        SELECT * FROM vw_analisis_preguntas 
        WHERE proceso_admision = :proceso 
        ORDER BY porcentaje_acierto DESC 
        LIMIT 10
    """), {"proceso": proceso}).fetchall()
    
    return templates.TemplateResponse(
        "admin/estadisticas.html",
        {
            "request": request,
            "usuario": usuario,
            "proceso_actual": proceso,
            "active_page": "estadisticas",
            "stats_generales": stats_generales,
            "stats_programa": stats_programa,
            "preguntas_dificiles": preguntas_dificiles,
            "preguntas_faciles": preguntas_faciles
        }
    )


# ============================================================
# API ENDPOINTS AUXILIARES
# ============================================================

@router.get("/api/postulante/{postulante_id}/detalle")
async def detalle_postulante(
    postulante_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Obtener detalle de un postulante"""
    result = db.execute(text("""
        SELECT 
            p.dni,
            p.nombres,
            p.apellido_paterno,
            p.apellido_materno,
            CONCAT(p.apellido_paterno, ' ', p.apellido_materno, ', ', p.nombres) as nombre_completo,
            p.programa_educativo,
            p.codigo_unico,
            hr.nota_final,
            hr.respuestas_correctas_count as respuestas_correctas,
            hr.estado,
            hr.fecha_captura,
            hr.fecha_calificacion
        FROM postulantes p
        LEFT JOIN hojas_respuestas hr ON hr.postulante_id = p.id
        WHERE p.id = :id
    """), {"id": postulante_id}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Postulante no encontrado")
    
    return dict(result._mapping)


@router.get("/api/ranking/exportar/excel")
async def exportar_ranking_excel(
    proceso: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Exportar ranking a Excel"""
    # TODO: Implementar servicio de exportación
    raise HTTPException(status_code=501, detail="Funcionalidad en desarrollo")
    # from app.services.exportacion import ExportacionService
    # servicio = ExportacionService(db)
    # excel_bytes = servicio.exportar_ranking_excel(proceso)
    # return StreamingResponse(
    #     excel_bytes,
    #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    #     headers={"Content-Disposition": f"attachment; filename=ranking_{proceso}.xlsx"}
    # )


@router.get("/api/ranking/exportar/pdf")
async def exportar_ranking_pdf(
    proceso: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Exportar ranking a PDF"""
    # TODO: Implementar servicio de exportación
    raise HTTPException(status_code=501, detail="Funcionalidad en desarrollo")
    # from app.services.exportacion import ExportacionService
    # servicio = ExportacionService(db)
    # pdf_bytes = servicio.exportar_ranking_pdf(proceso)
    # return StreamingResponse(
    #     pdf_bytes,
    #     media_type="application/pdf",
    #     headers={"Content-Disposition": f"attachment; filename=ranking_{proceso}.pdf"}
    # )


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def obtener_proceso_actual() -> str:
    """Obtener el proceso de admisión actual"""
    # Esto podría venir de configuración o calcularse
    return "2025-2"


def obtener_estadisticas_generales(db: Session, proceso: str) -> dict:
    """Obtener estadísticas generales del proceso"""
    result = db.execute(text("""
        SELECT 
            (SELECT COUNT(*) FROM postulantes WHERE proceso_admision = :proceso) as total_postulantes,
            (SELECT COUNT(*) FROM hojas_respuestas WHERE proceso_admision = :proceso AND estado IN ('PROCESADO', 'procesado')) as hojas_procesadas,
            (SELECT COUNT(*) FROM hojas_respuestas WHERE proceso_admision = :proceso AND nota_final IS NOT NULL) as hojas_calificadas,
            (SELECT AVG(nota_final) FROM hojas_respuestas WHERE proceso_admision = :proceso AND nota_final IS NOT NULL) as promedio_nota,
            (SELECT MAX(nota_final) FROM hojas_respuestas WHERE proceso_admision = :proceso) as nota_maxima,
            (SELECT MIN(nota_final) FROM hojas_respuestas WHERE proceso_admision = :proceso AND nota_final IS NOT NULL) as nota_minima
    """), {"proceso": proceso}).fetchone()
    
    return dict(result._mapping) if result else {}


def verificar_gabarito(db: Session, proceso: str) -> dict:
    """Verificar si existe gabarito para el proceso"""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            MIN(created_at) as fecha
        FROM clave_respuestas
        WHERE proceso_admision = :proceso
    """), {"proceso": proceso}).fetchone()
    
    return {
        "existe": result.total == 100,
        "total": result.total,
        "fecha": result.fecha.strftime("%d/%m/%Y %H:%M") if result.fecha else None
    }


def verificar_calificacion(db: Session, proceso: str) -> dict:
    """Verificar si se ha ejecutado la calificación"""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            MAX(fecha_calificacion) as fecha
        FROM hojas_respuestas
        WHERE proceso_admision = :proceso AND nota_final IS NOT NULL
    """), {"proceso": proceso}).fetchone()
    
    return {
        "ejecutada": result.total > 0,
        "total": result.total,
        "fecha": result.fecha.strftime("%d/%m/%Y %H:%M") if result.fecha else None
    }


def verificar_publicacion(db: Session, proceso: str) -> dict:
    """Verificar si los resultados están publicados"""
    result = db.execute(text("""
        SELECT 
            pr.fecha_publicacion,
            pr.autorizante_nombre,
            ua.nombres as publicado_por
        FROM publicaciones_resultados pr
        LEFT JOIN usuarios_admin ua ON ua.id = pr.publicado_por_id
        WHERE pr.proceso_admision = :proceso
        AND pr.estado = 'PUBLICADO'
        ORDER BY pr.fecha_publicacion DESC
        LIMIT 1
    """), {"proceso": proceso}).fetchone()
    
    return {
        "publicado": result is not None,
        "fecha": result.fecha_publicacion.strftime("%d/%m/%Y %H:%M") if result else None,
        "usuario": result.publicado_por if result else None
    }


def obtener_top_postulantes(db: Session, proceso: str, limit: int = 10) -> list:
    """Obtener top N postulantes"""
    result = db.execute(text("""
        SELECT 
            p.dni,
            CONCAT(p.apellido_paterno, ' ', p.apellido_materno, ', ', p.nombres) as nombre_completo,
            p.programa_educativo,
            hr.respuestas_correctas_count as respuestas_correctas,
            hr.nota_final
        FROM hojas_respuestas hr
        JOIN postulantes p ON p.id = hr.postulante_id
        WHERE hr.proceso_admision = :proceso AND hr.nota_final IS NOT NULL
        ORDER BY hr.nota_final DESC, hr.respuestas_correctas_count DESC
        LIMIT :limit
    """), {"proceso": proceso, "limit": limit}).fetchall()
    
    return [dict(r._mapping) for r in result]


def obtener_stats_por_programa(db: Session, proceso: str) -> list:
    """Obtener estadísticas por programa educativo"""
    result = db.execute(text("""
        SELECT 
            p.programa_educativo as nombre,
            COUNT(*) as total,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as porcentaje
        FROM postulantes p
        WHERE p.proceso_admision = :proceso
        GROUP BY p.programa_educativo
        ORDER BY total DESC
    """), {"proceso": proceso}).fetchall()
    
    return [dict(r._mapping) for r in result]


def obtener_actividad_reciente(db: Session, proceso: str) -> list:
    """Obtener actividad reciente del proceso"""
    result = db.execute(text("""
        SELECT 
            accion,
            detalles,
            created_at
        FROM auditoria_proceso
        WHERE proceso_admision = :proceso
        ORDER BY created_at DESC
        LIMIT 5
    """), {"proceso": proceso}).fetchall()
    
    actividades = []
    iconos = {
        "GABARITO_REGISTRADO": "✅",
        "CALIFICACION_EJECUTADA": "📝",
        "RESULTADOS_PUBLICADOS": "📢",
        "HOJA_CAPTURADA": "📸"
    }
    
    for r in result:
        actividades.append({
            "icono": iconos.get(r.accion, "📌"),
            "mensaje": r.accion.replace("_", " ").title(),
            "fecha": r.created_at.strftime("%d/%m %H:%M"),
            "tipo": "success" if "PUBLICADO" in r.accion else "info"
        })
    
    return actividades