"""
POSTULANDO - API de Calificación
app/api/calificacion.py

Endpoints para calificar hojas procesadas.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import get_db
from app.models import HojaRespuesta, Respuesta, ClaveRespuesta, Calificacion, Postulante

router = APIRouter()

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

async def calificar_hoja_individual(hoja_id: int, gabarito_id: int, db: Session):
    """
    Lógica de calificación de una hoja individual.
    """
    
    # Obtener hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        raise HTTPException(status_code=404, detail=f"Hoja {hoja_id} no encontrada")
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(ClaveRespuesta.id == gabarito_id).first()
    
    if not gabarito:
        raise HTTPException(status_code=404, detail="Gabarito no encontrado")
    
    # Respuestas correctas
    respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
    
    # Obtener respuestas del postulante
    respuestas_postulante = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    if not respuestas_postulante:
        raise HTTPException(
            status_code=400,
            detail=f"No hay respuestas registradas para la hoja {hoja_id}"
        )
    
    # Calificar
    correctas = 0
    incorrectas = 0
    en_blanco = 0
    no_legibles = 0
    
    for respuesta in respuestas_postulante:
        num_pregunta = str(respuesta.numero_pregunta)
        respuesta_correcta = respuestas_correctas.get(num_pregunta)
        
        # Solo calificar respuestas válidas (A-E)
        if respuesta.respuesta_marcada in ['A', 'B', 'C', 'D', 'E']:
            if respuesta.respuesta_marcada == respuesta_correcta:
                respuesta.es_correcta = True
                correctas += 1
            else:
                respuesta.es_correcta = False
                incorrectas += 1
        
        elif respuesta.respuesta_marcada == 'VACIO':
            en_blanco += 1
        
        else:
            # LETRA_INVALIDA, GARABATO, MULTIPLE, ILEGIBLE
            no_legibles += 1
    
    db.commit()
    
    # Calcular nota (sobre 20, sistema vigesimal peruano)
    total_preguntas = len(respuestas_postulante)
    porcentaje = (correctas / total_preguntas) * 100 if total_preguntas > 0 else 0
    nota_final = (correctas / total_preguntas) * 20 if total_preguntas > 0 else 0
    
    # Nota mínima de aprobación (típicamente 10.5 en Perú)
    nota_minima = 10.5
    aprobado = nota_final >= nota_minima
    
    # Actualizar hoja
    hoja.nota_final = round(nota_final, 2)
    hoja.respuestas_correctas_count = correctas
    hoja.estado = "calificado"
    
    # Crear o actualizar registro en tabla calificaciones
    calificacion_existente = db.query(Calificacion).filter(
        Calificacion.postulante_id == hoja.postulante_id
    ).first()
    
    if calificacion_existente:
        # Actualizar
        calificacion_existente.nota = round(nota_final, 2)
        calificacion_existente.correctas = correctas
        calificacion_existente.incorrectas = incorrectas
        calificacion_existente.en_blanco = en_blanco
        calificacion_existente.no_legibles = no_legibles
        calificacion_existente.porcentaje_aciertos = round(porcentaje, 2)
        calificacion_existente.aprobado = aprobado
        calificacion_existente.nota_minima = nota_minima
        calificacion_existente.calificado_at = datetime.now()
    else:
        # Crear nuevo
        calificacion = Calificacion(
            postulante_id=hoja.postulante_id,
            nota=round(nota_final, 2),
            correctas=correctas,
            incorrectas=incorrectas,
            en_blanco=en_blanco,
            no_legibles=no_legibles,
            porcentaje_aciertos=round(porcentaje, 2),
            aprobado=aprobado,
            nota_minima=nota_minima,
            calificado_at=datetime.now()
        )
        db.add(calificacion)
    
    db.commit()
    
    return {
        "success": True,
        "hoja_id": hoja_id,
        "codigo_hoja": hoja.codigo_hoja,
        "nota_final": round(nota_final, 2),
        "correctas": correctas,
        "incorrectas": incorrectas,
        "en_blanco": en_blanco,
        "no_legibles": no_legibles,
        "total": total_preguntas,
        "porcentaje": round(porcentaje, 2),
        "aprobado": aprobado
    }

# ============================================================================
# ENDPOINTS DE CALIFICACIÓN
# ============================================================================

@router.post("/calificar-hojas-pendientes")
async def calificar_hojas_pendientes(
    proceso_admision: str = "2025-2",
    db: Session = Depends(get_db)
):
    """Califica todas las hojas pendientes después de registrar gabarito"""
    
    try:
        # Verificar gabarito
        gabarito = db.query(ClaveRespuesta).filter_by(
            proceso_admision=proceso_admision
        ).first()
        
        if not gabarito:
            raise HTTPException(
                status_code=400,
                detail=f"No existe gabarito para {proceso_admision}"
            )
        
        # Obtener pendientes
        hojas_pendientes = db.query(HojaRespuesta).filter_by(
            estado="pendiente_calificar",
            proceso_admision=proceso_admision
        ).all()
        
        if not hojas_pendientes:
            return {
                "success": True,
                "mensaje": "No hay hojas pendientes",
                "calificadas": 0
            }
        
        calificadas = 0
        errores = []
        
        for hoja in hojas_pendientes:
            try:
                # Obtener respuestas
                respuestas = db.query(Respuesta).filter_by(
                    hoja_respuesta_id=hoja.id
                ).order_by(Respuesta.numero_pregunta).all()
                
                respuestas_array = [r.respuesta_marcada for r in respuestas]
                
                # Calificar
                from app.services import calcular_calificacion
                calificacion = calcular_calificacion(
                    respuestas_array,
                    proceso_admision,
                    db
                )
                
                # Actualizar
                hoja.nota_final = calificacion["nota"]
                hoja.respuestas_correctas_count = calificacion["correctas"]
                hoja.estado = "completado"
                hoja.fecha_calificacion = datetime.now()
                
                calificadas += 1
                
            except Exception as e:
                errores.append({"hoja_id": hoja.id, "error": str(e)})
        
        db.commit()
        
        return {
            "success": True,
            "calificadas": calificadas,
            "errores": errores
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calificar-hojas")
async def calificar_hojas_masivo(
    proceso: str = "2025-2",
    db: Session = Depends(get_db)
):
    """
    Califica TODAS las hojas procesadas que aún no han sido calificadas.
    Compara con el gabarito del proceso.
    """
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso
    ).first()
    
    if not gabarito:
        raise HTTPException(
            status_code=404,
            detail=f"No existe gabarito para el proceso {proceso}"
        )
    
    # Obtener hojas procesadas sin calificar
    hojas_sin_calificar = db.query(HojaRespuesta).filter(
        HojaRespuesta.estado == "procesado"
    ).all()
    
    if not hojas_sin_calificar:
        return {
            "success": True,
            "message": "No hay hojas pendientes de calificar",
            "calificadas": 0
        }
    
    resultados = []
    
    for hoja in hojas_sin_calificar:
        try:
            resultado = await calificar_hoja_individual(hoja.id, gabarito.id, db)
            resultados.append(resultado)
        except Exception as e:
            print(f"Error al calificar hoja {hoja.id}: {e}")
            continue
    
    return {
        "success": True,
        "message": f"Calificación completada",
        "total_hojas": len(hojas_sin_calificar),
        "calificadas": len(resultados),
        "resultados": resultados
    }


@router.post("/calificar-hoja/{hoja_id}")
async def calificar_hoja_endpoint(
    hoja_id: int,
    gabarito_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Califica una hoja específica.
    """
    
    # Si no se especifica gabarito, usar el activo
    if not gabarito_id:
        gabarito = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == "2025-2"
        ).first()
        
        if not gabarito:
            raise HTTPException(
                status_code=404,
                detail="No hay gabarito activo"
            )
        
        gabarito_id = gabarito.id
    
    resultado = await calificar_hoja_individual(hoja_id, gabarito_id, db)
    
    return resultado