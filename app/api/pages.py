"""
POSTULANDO - Rutas de Páginas HTML
app/api/pages.py

Todas las rutas que retornan templates HTML.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, text

from app.database import get_db
from app.models import (
    Postulante, HojaRespuesta, ClaveRespuesta,
    Calificacion, Profesor, Aula, Respuesta
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def obtener_estadisticas(db: Session):
    """Obtiene estadísticas generales del sistema"""
    total_postulantes = db.query(func.count(Postulante.id)).scalar() or 0
    hojas_procesadas = db.query(func.count(HojaRespuesta.id)).scalar() or 0
    respuestas_correctas = db.query(func.count(ClaveRespuesta.id)).scalar() or 0
    calificados = db.query(func.count(Calificacion.id)).scalar() or 0
    
    return {
        "total_postulantes": total_postulantes,
        "hojas_procesadas": hojas_procesadas,
        "gabarito_cargado": respuestas_correctas == 100,
        "respuestas_correctas": respuestas_correctas,
        "calificados": calificados
    }

# ============================================================================
# PÁGINAS HTML
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Página principal - Dashboard"""
    stats = obtener_estadisticas(db)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats
    })


@router.get("/generar-hojas", response_class=HTMLResponse)
async def generar_hojas_page(request: Request, db: Session = Depends(get_db)):
    """Página para generar hojas de respuestas"""
    postulantes = db.query(Postulante).order_by(Postulante.id).all()
    return templates.TemplateResponse("generar_hojas.html", {
        "request": request,
        "total_postulantes": len(postulantes),
        "postulantes": postulantes
    })


@router.get("/capturar-hojas", response_class=HTMLResponse)
async def capturar_hojas_page(request: Request, db: Session = Depends(get_db)):
    """Página para capturar hojas con cámara"""
    total_postulantes = db.query(func.count(Postulante.id)).scalar() or 0
    hojas_procesadas = db.query(func.count(HojaRespuesta.id)).scalar() or 0
    
    return templates.TemplateResponse("capturar_hojas.html", {
        "request": request,
        "total_postulantes": total_postulantes,
        "hojas_procesadas": hojas_procesadas
    })


@router.get("/registrar-gabarito", response_class=HTMLResponse)
async def registrar_gabarito_page(request: Request, db: Session = Depends(get_db)):
    """Página para registrar respuestas correctas"""
    gabarito_existe_flag = db.query(func.count(ClaveRespuesta.id)).scalar() > 0
    
    return templates.TemplateResponse("registrar_gabarito.html", {
        "request": request,
        "gabarito_ya_existe": gabarito_existe_flag
    })


@router.get("/gabarito/confirmar", response_class=HTMLResponse)
async def pagina_confirmar_gabarito(request: Request):
    """
    Muestra página de confirmación con estadísticas.
    Los datos vienen de sessionStorage (JavaScript).
    """
    return templates.TemplateResponse("confirmar_gabarito.html", {
        "request": request
    })


@router.get("/resultados", response_class=HTMLResponse)
async def pagina_resultados(
    request: Request,
    codigo: str = None,
    estado: str = None,
    api: str = None,
    db: Session = Depends(get_db)
):
    """
    Página de resultados con todas las hojas procesadas.
    Más recientes primero.
    """
    
    # Query base
    query = db.query(HojaRespuesta)
    
    # Aplicar filtros si existen
    if codigo:
        query = query.filter(HojaRespuesta.codigo_hoja.ilike(f'%{codigo}%'))
    
    if estado:
        query = query.filter(HojaRespuesta.estado == estado)
    
    if api:
        query = query.filter(HojaRespuesta.api_utilizada == api)
    
    # Ordenar por más recientes primero
    hojas = query.order_by(desc(HojaRespuesta.created_at)).limit(50).all()
    
    # Calcular estadísticas para cada hoja
    hojas_con_stats = []
    
    for hoja in hojas:
        # Obtener estadísticas de respuestas
        respuestas = db.query(Respuesta).filter(
            Respuesta.hoja_respuesta_id == hoja.id
        ).all()
        
        validas = sum(1 for r in respuestas if r.respuesta_marcada in ['A', 'B', 'C', 'D', 'E'])
        vacias = sum(1 for r in respuestas if r.respuesta_marcada == 'VACIO')
        problematicas = sum(1 for r in respuestas if r.respuesta_marcada in ['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
        
        # Obtener DNI del postulante
        dni_postulante = None
        if hoja.postulante_id:
            postulante = db.query(Postulante).filter(Postulante.id == hoja.postulante_id).first()
            if postulante:
                dni_postulante = postulante.dni
        
        hojas_con_stats.append({
            'id': hoja.id,
            'codigo_hoja': hoja.codigo_hoja,
            'dni_postulante': dni_postulante or '—',
            'codigo_aula': hoja.codigo_aula or '—',
            'api_utilizada': hoja.api_utilizada or 'N/A',
            'tiempo_procesamiento': hoja.tiempo_procesamiento or 0,
            'fecha_captura': hoja.created_at,
            'stats': {
                'validas': validas,
                'vacias': vacias,
                'problematicas': problematicas
            }
        })
    
    # Estadísticas globales
    total_hojas = db.query(func.count(HojaRespuesta.id)).scalar()
    
    total_respuestas = db.query(Respuesta).count()
    total_validas = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada.in_(['A', 'B', 'C', 'D', 'E'])
    ).count()
    total_vacias = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada == 'VACIO'
    ).count()
    total_problematicas = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada.in_(['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
    ).count()
    
    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "hojas": hojas_con_stats,
        "total_hojas": total_hojas,
        "total_validas": total_validas,
        "total_vacias": total_vacias,
        "total_problematicas": total_problematicas
    })


@router.get("/hoja/{hoja_id}/detalle", response_class=HTMLResponse)
async def detalle_hoja(
    hoja_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Página de detalle de una hoja específica.
    Muestra las 100 respuestas con su clasificación.
    """
    
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Hoja no encontrada")
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    return templates.TemplateResponse("detalle_hoja.html", {
        "request": request,
        "hoja": hoja,
        "respuestas": respuestas
    })


@router.get("/estadisticas", response_class=HTMLResponse)
async def pagina_estadisticas(request: Request, db: Session = Depends(get_db)):
    """
    Página de estadísticas generales y ranking.
    """
    
    # Estadísticas generales
    total_postulantes = db.query(func.count(Postulante.id)).scalar()
    
    examenes_calificados = db.query(func.count(HojaRespuesta.id)).filter(
        HojaRespuesta.estado == "calificado"
    ).scalar()
    
    calificaciones = db.query(Calificacion).all()
    
    if calificaciones:
        notas = [c.nota for c in calificaciones]
        nota_promedio = sum(notas) / len(notas)
        nota_maxima = max(notas)
        nota_minima = min(notas)
        aprobados = sum(1 for c in calificaciones if c.aprobado)
        desaprobados = len(calificaciones) - aprobados
    else:
        nota_promedio = 0
        nota_maxima = 0
        nota_minima = 0
        aprobados = 0
        desaprobados = 0
    
    stats = {
        "total_postulantes": total_postulantes or 0,
        "examenes_calificados": examenes_calificados or 0,
        "nota_promedio": nota_promedio,
        "nota_maxima": nota_maxima,
        "nota_minima": nota_minima,
        "aprobados": aprobados,
        "desaprobados": desaprobados
    }
    
    # Ranking
    try:
        # Intentar usar la vista
        ranking_query = text("""
            SELECT * FROM vw_ranking_postulantes
            ORDER BY ranking ASC
            LIMIT 50
        """)
        ranking = db.execute(ranking_query).fetchall()
        
        # Convertir a lista de dicts
        ranking_list = []
        for row in ranking:
            ranking_list.append({
                "ranking": row.ranking,
                "dni": row.dni,
                "nombre_completo": row.nombre_completo,
                "programa_educativo": row.programa_educativo,
                "nota": row.nota,
                "respuestas_correctas": row.respuestas_correctas
            })
    except:
        # Si no existe la vista, calcular manualmente
        ranking_data = db.query(
            Postulante,
            Calificacion
        ).join(
            Calificacion, Postulante.id == Calificacion.postulante_id
        ).order_by(
            Calificacion.nota.desc()
        ).limit(50).all()
        
        ranking_list = []
        for i, (postulante, calificacion) in enumerate(ranking_data, 1):
            ranking_list.append({
                "ranking": i,
                "dni": postulante.dni,
                "nombre_completo": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa_educativo": postulante.programa_educativo,
                "nota": calificacion.nota,
                "respuestas_correctas": calificacion.correctas
            })
    
    return templates.TemplateResponse("estadisticas.html", {
        "request": request,
        "stats": stats,
        "ranking": ranking_list
    })


@router.get("/revision-manual", response_class=HTMLResponse)
async def pagina_revision_manual(
    request: Request,
    hoja: str = None,
    tipo: str = None,
    db: Session = Depends(get_db)
):
    """
    Página de revisión manual de respuestas problemáticas.
    """
    
    # Query base: respuestas que requieren revisión
    query = db.query(Respuesta).join(HojaRespuesta).filter(
        or_(
            Respuesta.requiere_revision == True,
            Respuesta.respuesta_marcada.in_(['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
        )
    )
    
    # Aplicar filtros
    if hoja:
        query = query.filter(HojaRespuesta.codigo_hoja.ilike(f'%{hoja}%'))
    
    if tipo:
        if tipo == 'baja_confianza':
            query = query.filter(Respuesta.confianza < 0.7)
        else:
            query = query.filter(Respuesta.respuesta_marcada == tipo)
    
    respuestas = query.order_by(HojaRespuesta.codigo_hoja, Respuesta.numero_pregunta).all()
    
    # Preparar datos
    respuestas_data = []
    for resp in respuestas:
        respuestas_data.append({
            'id': resp.id,
            'numero_pregunta': resp.numero_pregunta,
            'hoja_codigo': resp.hoja_respuesta.codigo_hoja,
            'respuesta_marcada': resp.respuesta_marcada,
            'confianza': resp.confianza,
            'observacion': resp.observacion,
            'tipo_problema': resp.respuesta_marcada if resp.respuesta_marcada not in ['A','B','C','D','E'] else 'baja_confianza',
            'imagen_url': resp.hoja_respuesta.imagen_url
        })
    
    # Estadísticas
    total_pendientes = len(respuestas_data)
    letra_invalida = sum(1 for r in respuestas_data if r['tipo_problema'] == 'LETRA_INVALIDA')
    garabatos = sum(1 for r in respuestas_data if r['tipo_problema'] == 'GARABATO')
    baja_confianza = sum(1 for r in respuestas_data if r['tipo_problema'] == 'baja_confianza')
    
    return templates.TemplateResponse("revision_manual.html", {
        "request": request,
        "respuestas": respuestas_data,
        "total_pendientes": total_pendientes,
        "letra_invalida": letra_invalida,
        "garabatos": garabatos,
        "baja_confianza": baja_confianza
    })


@router.get("/asignar-postulantes", response_class=HTMLResponse)
async def pagina_asignar_postulantes(request: Request, db: Session = Depends(get_db)):
    """
    Página para asignar postulantes a aulas automáticamente.
    """
    return templates.TemplateResponse("asignar_postulantes.html", {
        "request": request
    })