"""
POSTULANDO - API de Revisión Manual
app/api/revision.py

Endpoints para revisar y corregir respuestas problemáticas manualmente.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import Respuesta, ClaveRespuesta

router = APIRouter()

# ============================================================================
# ENDPOINTS DE REVISIÓN MANUAL
# ============================================================================

@router.put("/corregir-respuesta/{respuesta_id}")
async def corregir_respuesta_individual(
    respuesta_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Corrige una respuesta individual después de revisión manual.
    """
    
    respuesta_corregida = data.get('respuesta_corregida')
    
    # Validar
    if not respuesta_corregida or respuesta_corregida not in ['A', 'B', 'C', 'D', 'E']:
        raise HTTPException(
            status_code=400,
            detail="La respuesta debe ser A, B, C, D o E"
        )
    
    # Obtener respuesta
    respuesta = db.query(Respuesta).filter(Respuesta.id == respuesta_id).first()
    
    if not respuesta:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    
    # Guardar respuesta original en observación
    if not respuesta.observacion:
        respuesta.observacion = f"Original: {respuesta.respuesta_marcada}"
    else:
        respuesta.observacion += f" | Corregido de: {respuesta.respuesta_marcada}"
    
    # Actualizar
    respuesta.respuesta_marcada = respuesta_corregida
    respuesta.requiere_revision = False
    respuesta.confianza = 1.0  # Corregida manualmente = 100% confianza
    
    # Recalcular si es correcta (comparar con gabarito)
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == "2025-2"
    ).first()
    
    if gabarito:
        respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
        respuesta_correcta = respuestas_correctas.get(str(respuesta.numero_pregunta))
        respuesta.es_correcta = (respuesta_corregida == respuesta_correcta)
    
    db.commit()
    
    return {
        "success": True,
        "message": "Respuesta corregida",
        "respuesta_id": respuesta_id,
        "nueva_respuesta": respuesta_corregida,
        "es_correcta": respuesta.es_correcta
    }


@router.put("/corregir-respuestas-masivo")
async def corregir_respuestas_masivo(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Corrige múltiples respuestas a la vez.
    
    data: {"correcciones": {respuesta_id: nueva_respuesta}}
    """
    
    correcciones = data.get('correcciones', {})
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == "2025-2"
    ).first()
    
    respuestas_correctas = {}
    if gabarito:
        respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
    
    corregidas = 0
    
    for respuesta_id, nueva_respuesta in correcciones.items():
        # Validar
        if nueva_respuesta not in ['A', 'B', 'C', 'D', 'E']:
            continue
        
        # Obtener respuesta
        respuesta = db.query(Respuesta).filter(Respuesta.id == int(respuesta_id)).first()
        
        if not respuesta:
            continue
        
        # Guardar original
        if not respuesta.observacion:
            respuesta.observacion = f"Original: {respuesta.respuesta_marcada}"
        else:
            respuesta.observacion += f" | Corregido de: {respuesta.respuesta_marcada}"
        
        # Actualizar
        respuesta.respuesta_marcada = nueva_respuesta
        respuesta.requiere_revision = False
        respuesta.confianza = 1.0
        
        # Verificar si es correcta
        if respuestas_correctas:
            respuesta_correcta = respuestas_correctas.get(str(respuesta.numero_pregunta))
            respuesta.es_correcta = (nueva_respuesta == respuesta_correcta)
        
        corregidas += 1
    
    db.commit()
    
    # Recalcular notas de las hojas afectadas
    # (opcional, se puede hacer después)
    
    return {
        "success": True,
        "message": f"{corregidas} respuestas corregidas",
        "corregidas": corregidas
    }