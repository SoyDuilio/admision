"""
API Endpoints para la DEMO
Maneja todas las operaciones de la demostración
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import uuid
from pathlib import Path
from datetime import datetime
import logging

from fastapi.responses import HTMLResponse

from app.database import get_db
from app.config import settings
from app.models.postulante import Postulante
from app.models.hoja_respuesta import HojaRespuesta
from app.models.respuesta import Respuesta
from app.models.clave_respuesta import ClaveRespuesta
from app.models.calificacion import Calificacion
from app.schemas.postulante import PostulanteListItem, PostulanteSelector
from app.schemas.respuesta import (
    EstadisticasDemo,
    VisionAPIResponse,
    CalificacionResponse,
    ResultadoCompleto
)
from app.services.vision_orchestrator import vision_orchestrator
from app.models.clave_respuesta import ClaveRespuesta

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== POSTULANTES ====================

@router.get("/postulantes", response_model=List[PostulanteSelector])
async def get_postulantes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de postulantes para el selector
    """
    postulantes = db.query(Postulante)\
        .filter(Postulante.activo == True)\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return [
        PostulanteSelector(
            id=p.id,
            dni=p.dni,
            nombre_completo=p.nombre_completo,
            codigo=p.codigo
        )
        for p in postulantes
    ]


@router.get("/postulantes/{postulante_id}")
async def get_postulante(
    postulante_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene información de un postulante específico"""
    postulante = db.query(Postulante).filter(Postulante.id == postulante_id).first()
    
    if not postulante:
        raise HTTPException(status_code=404, detail="Postulante no encontrado")
    
    return postulante.to_dict()


# ==================== CAPTURA DE HOJAS ====================

@router.post("/capturar/estudiante")
async def capturar_hoja_estudiante(
    postulante_id: int = Form(...),
    imagen: UploadFile = File(...),
    latitud: Optional[float] = Form(None),
    longitud: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Captura y procesa la hoja de respuestas de un estudiante
    
    1. Guarda la imagen en uploads/
    2. Procesa con Vision APIs
    3. Guarda respuestas en BD
    """
    try:
        # Verificar que el postulante existe
        postulante = db.query(Postulante).filter(Postulante.id == postulante_id).first()
        if not postulante:
            raise HTTPException(status_code=404, detail="Postulante no encontrado")
        
        # Verificar que no tenga ya un examen procesado
        examen_previo = db.query(HojaRespuesta)\
            .filter(HojaRespuesta.postulante_id == postulante_id)\
            .filter(HojaRespuesta.estado == "completado")\
            .first()
        
        if examen_previo:
            raise HTTPException(
                status_code=400,
                detail="Este postulante ya tiene un examen procesado"
            )
        
        # Guardar imagen
        imagen_filename = f"{uuid.uuid4()}_{imagen.filename}"
        imagen_path = Path(settings.upload_dir) / imagen_filename
        
        with open(imagen_path, "wb") as f:
            content = await imagen.read()
            f.write(content)
        
        imagen_size_kb = len(content) // 1024
        
        logger.info(f"📁 Imagen guardada: {imagen_path} ({imagen_size_kb} KB)")
        
        # Crear registro de hoja de respuesta
        hoja = HojaRespuesta(
            postulante_id=postulante_id,
            imagen_path=str(imagen_path),
            imagen_size_kb=imagen_size_kb,
            latitud=latitud,
            longitud=longitud,
            procesada=False
        )
        db.add(hoja)
        db.commit()
        db.refresh(hoja)
        
        # Procesar con Vision APIs
        logger.info(f"🔍 Procesando imagen con Vision APIs...")
        
        result = await vision_orchestrator.process_image(
            image_path=str(imagen_path),
            tipo="estudiante"
        )
        
        if not result.success:
            hoja.error_message = result.error_message
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando imagen: {result.error_message}"
            )
        
        # Actualizar hoja con resultados
        hoja.procesada = True
        hoja.api_usada = result.api_usada
        hoja.tiempo_procesamiento = result.tiempo_procesamiento
        hoja.respuestas_detectadas = result.total_detectadas
        hoja.confianza_promedio = result.confianza_promedio
        hoja.processed_at = datetime.utcnow()
        
        # Guardar respuestas individuales
        for respuesta_detectada in result.respuestas:
            respuesta = Respuesta(
                hoja_respuesta_id=hoja.id,
                numero_pregunta=respuesta_detectada.numero_pregunta,
                respuesta=respuesta_detectada.respuesta,
                confianza=respuesta_detectada.confianza
            )
            db.add(respuesta)
        
        # Marcar postulante como examinado
        postulante.examen_rendido = True
        
        db.commit()
        
        logger.info(f"✅ Hoja procesada correctamente para {postulante.nombre_completo}")
        
        return {
            "success": True,
            "message": "Hoja procesada correctamente",
            "hoja_id": hoja.id,
            "api_usada": result.api_usada,
            "tiempo_procesamiento": result.tiempo_procesamiento,
            "respuestas_detectadas": result.total_detectadas,
            "confianza_promedio": result.confianza_promedio
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en captura: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capturar/clave")
async def capturar_clave_respuestas(
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Captura y procesa la clave de respuestas correctas
    
    1. Guarda la imagen
    2. Procesa con Vision APIs
    3. Guarda las 100 respuestas correctas en BD
    """
    try:
        # Verificar si ya existe una clave
        clave_existente = db.query(ClaveRespuesta).first()
        if clave_existente:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una clave de respuestas cargada. Elimínala primero."
            )
        
        # Guardar imagen
        imagen_filename = f"clave_{uuid.uuid4()}_{imagen.filename}"
        imagen_path = Path(settings.upload_dir) / imagen_filename
        
        with open(imagen_path, "wb") as f:
            content = await imagen.read()
            f.write(content)
        
        logger.info(f"📁 Clave guardada: {imagen_path}")
        
        # Procesar con Vision APIs
        logger.info(f"🔍 Procesando clave con Vision APIs...")
        
        result = await vision_orchestrator.process_image(
            image_path=str(imagen_path),
            tipo="clave"
        )
        
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando clave: {result.error_message}"
            )
        
        # Validar que tengamos 100 respuestas
        if result.total_detectadas != 100:
            raise HTTPException(
                status_code=400,
                detail=f"La clave debe tener 100 respuestas. Se detectaron {result.total_detectadas}"
            )
        
        # Guardar clave de respuestas
        for respuesta_detectada in result.respuestas:
            if respuesta_detectada.respuesta is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"La pregunta {respuesta_detectada.numero_pregunta} no tiene respuesta"
                )
            
            clave = ClaveRespuesta(
                numero_pregunta=respuesta_detectada.numero_pregunta,
                respuesta_correcta=respuesta_detectada.respuesta,
                imagen_path=str(imagen_path),
                api_usada=result.api_usada
            )
            db.add(clave)
        
        db.commit()
        
        logger.info(f"✅ Clave de respuestas procesada correctamente")
        
        return {
            "success": True,
            "message": "Clave procesada correctamente",
            "api_usada": result.api_usada,
            "tiempo_procesamiento": result.tiempo_procesamiento,
            "total_respuestas": result.total_detectadas
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error procesando clave: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CALIFICACIÓN ====================

@router.post("/calificar/todos")
async def calificar_todos(db: Session = Depends(get_db)):
    """
    Califica todos los exámenes procesados comparándolos con la clave
    """
    try:
        # Verificar que exista la clave
        clave_count = db.query(ClaveRespuesta).count()
        if clave_count != 100:
            raise HTTPException(
                status_code=400,
                detail="Primero debes cargar la clave de respuestas"
            )
        
        # Obtener clave
        clave_dict = {
            c.numero_pregunta: c.respuesta_correcta
            for c in db.query(ClaveRespuesta).all()
        }
        
        # Obtener hojas procesadas
        hojas = db.query(HojaRespuesta)\
            .filter(HojaRespuesta.estado == "completado")\
            .all()
        
        if not hojas:
            raise HTTPException(
                status_code=400,
                detail="No hay exámenes para calificar"
            )
        
        calificados = 0
        
        for hoja in hojas:
            # Verificar si ya tiene calificación
            calificacion_existente = db.query(Calificacion)\
                .filter(Calificacion.postulante_id == hoja.postulante_id)\
                .first()
            
            if calificacion_existente:
                logger.info(f"⏭️ Postulante {hoja.postulante_id} ya tiene calificación")
                continue
            
            # Obtener respuestas del estudiante
            respuestas = db.query(Respuesta)\
                .filter(Respuesta.hoja_respuesta_id == hoja.id)\
                .all()
            
            # Calificar
            correctas = 0
            incorrectas = 0
            en_blanco = 0
            no_legibles = 0
            
            for respuesta in respuestas:
                clave_correcta = clave_dict.get(respuesta.numero_pregunta)
                
                if respuesta.respuesta is None:
                    en_blanco += 1
                    respuesta.es_correcta = False
                elif respuesta.respuesta == "?":
                    no_legibles += 1
                    respuesta.es_correcta = False
                elif respuesta.respuesta == clave_correcta:
                    correctas += 1
                    respuesta.es_correcta = True
                else:
                    incorrectas += 1
                    respuesta.es_correcta = False
            
            # Crear calificación
            nota = correctas  # Nota es igual a respuestas correctas (0-100)
            aprobado = nota >= 70  # Nota mínima 70
            
            calificacion = Calificacion(
                postulante_id=hoja.postulante_id,
                nota=nota,
                correctas=correctas,
                incorrectas=incorrectas,
                en_blanco=en_blanco,
                no_legibles=no_legibles,
                aprobado=aprobado,
                nota_minima=70,
                calificado_at=datetime.utcnow()
            )
            
            calificacion.calcular_porcentaje()
            
            db.add(calificacion)
            calificados += 1
        
        # Calcular puestos
        calificaciones = db.query(Calificacion)\
            .order_by(Calificacion.nota.desc())\
            .all()
        
        for idx, cal in enumerate(calificaciones, start=1):
            cal.puesto = idx
        
        db.commit()
        
        logger.info(f"✅ {calificados} exámenes calificados")
        
        return {
            "success": True,
            "message": f"{calificados} exámenes calificados correctamente",
            "total_calificados": calificados
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en calificación: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== RESULTADOS ====================

@router.get("/resultados", response_model=List[ResultadoCompleto])
async def get_resultados(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene los resultados de todos los exámenes calificados
    Ordenados por puesto (nota descendente)
    """
    calificaciones = db.query(Calificacion)\
        .join(Postulante)\
        .order_by(Calificacion.puesto)\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    resultados = []
    for cal in calificaciones:
        resultados.append(ResultadoCompleto(
            postulante=PostulanteListItem.model_validate(cal.postulante),
            calificacion=CalificacionResponse.model_validate(cal)
        ))
    
    return resultados


# ==================== ESTADÍSTICAS ====================

@router.get("/api/estadisticas")
async def get_estadisticas(db: Session = Depends(get_db)):
    """Obtiene estadísticas generales para la demo"""
    try:
        # Total de postulantes
        total_postulantes = db.query(Postulante).count()
        
        # Exámenes capturados (hojas con estado completado)
        examenes_capturados = db.query(HojaRespuesta)\
            .filter(HojaRespuesta.estado == 'completado')\
            .count()
        
        # Exámenes calificados (hojas que tienen nota)
        examenes_calificados = db.query(HojaRespuesta)\
            .filter(HojaRespuesta.nota_final.isnot(None))\
            .count()
        
        # Verificar si hay clave cargada
        clave_cargada = db.query(ClaveRespuesta).count() > 0
        
        return {
            "total_postulantes": total_postulantes,
            "examenes_capturados": examenes_capturados,
            "examenes_calificados": examenes_calificados,
            "clave_cargada": clave_cargada
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== UTILIDADES ====================

@router.delete("/limpiar/todo")
async def limpiar_todo(db: Session = Depends(get_db)):
    """
    CUIDADO: Limpia TODAS las hojas, respuestas, calificaciones y clave
    Útil para resetear la demo
    """
    if not settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="Solo disponible en modo demo"
        )
    
    try:
        # Eliminar en orden correcto por dependencias
        db.query(Calificacion).delete()
        db.query(Respuesta).delete()
        db.query(HojaRespuesta).delete()
        db.query(ClaveRespuesta).delete()
        
        # Resetear estado de postulantes
        db.query(Postulante).update({"examen_rendido": False})
        
        db.commit()
        
        logger.info("🧹 Demo limpiada completamente")
        
        return {
            "success": True,
            "message": "Demo limpiada correctamente"
        }
        
    except Exception as e:
        logger.error(f"❌ Error limpiando demo: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vision/status")
async def get_vision_status():
    """Obtiene el estado de las Vision APIs"""
    return {
        "apis_disponibles": vision_orchestrator.get_available_apis(),
        "estado": vision_orchestrator.get_api_status(),
        "orden_prioridad": vision_orchestrator.priority_order
    }



@router.get("/api/estadisticas-html", response_class=HTMLResponse)
async def get_estadisticas_html(db: Session = Depends(get_db)):
    """Devuelve las estadísticas en formato HTML para HTMX"""
    stats = await get_estadisticas(db)
    
    html = f"""
    <div class="stat-card">
        <div class="stat-value">{stats['total_postulantes']}</div>
        <div class="stat-label">Total Postulantes</div>
    </div>
    <div class="stat-card" style="background: linear-gradient(135deg, #10b981, #059669);">
        <div class="stat-value">{stats['examenes_capturados']}</div>
        <div class="stat-label">Exámenes Capturados</div>
    </div>
    <div class="stat-card" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
        <div class="stat-value">{stats['examenes_calificados']}</div>
        <div class="stat-label">Exámenes Calificados</div>
    </div>
    <div class="stat-card" style="background: linear-gradient(135deg, #8b5cf6, #7c3aed);">
        <div class="stat-value">{'✅' if stats['clave_cargada'] else '❌'}</div>
        <div class="stat-label">Clave Cargada</div>
    </div>
    """
    
    return html


@router.get("/api/postulantes")
async def get_postulantes(db: Session = Depends(get_db)):
    """Devuelve la lista de postulantes para el select"""
    postulantes = db.query(Postulante)\
        .order_by(Postulante.nombres)\
        .all()
    
    return [
        {
            "id": p.id,
            "dni": p.dni,
            "nombre_completo": p.nombre_completo,
            "codigo_unico": p.codigo_unico
        }
        for p in postulantes
    ]