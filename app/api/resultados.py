"""
POSTULANDO - API de Resultados y Estadísticas
app/api/resultados.py

Endpoints para consultar resultados, rankings y exportar datos.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from io import BytesIO
import pandas as pd

from app.database import get_db
from app.models import HojaRespuesta, Postulante, Respuesta

router = APIRouter()

# ============================================================================
# ENDPOINTS DE RESULTADOS
# ============================================================================

@router.get("/resultados/{proceso_admision}")
async def obtener_resultados(
    proceso_admision: str,
    db: Session = Depends(get_db)
):
    """Obtiene ranking de postulantes"""
    
    hojas = db.query(HojaRespuesta).filter(
        HojaRespuesta.proceso_admision == proceso_admision,
        HojaRespuesta.estado == "completado",
        HojaRespuesta.nota_final.isnot(None)
    ).order_by(HojaRespuesta.nota_final.desc()).all()
    
    resultados = []
    for i, hoja in enumerate(hojas, 1):
        postulante = hoja.postulante
        if postulante:
            resultados.append({
                "puesto": i,
                "dni": postulante.dni,
                "nombres": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa": postulante.programa_educativo,
                "nota": hoja.nota_final,
                "correctas": hoja.respuestas_correctas_count
            })
    
    return {
        "success": True,
        "proceso": proceso_admision,
        "total": len(resultados),
        "resultados": resultados
    }


@router.get("/exportar-resultados")
async def exportar_resultados_excel(db: Session = Depends(get_db)):
    """
    Exporta los resultados a Excel.
    """
    
    # Obtener todas las hojas
    hojas = db.query(HojaRespuesta).order_by(desc(HojaRespuesta.created_at)).all()
    
    data = []
    
    for hoja in hojas:
        respuestas = db.query(Respuesta).filter(
            Respuesta.hoja_respuesta_id == hoja.id
        ).all()
        
        validas = sum(1 for r in respuestas if r.respuesta_marcada in ['A', 'B', 'C', 'D', 'E'])
        vacias = sum(1 for r in respuestas if r.respuesta_marcada == 'VACIO')
        invalidas = sum(1 for r in respuestas if r.respuesta_marcada == 'LETRA_INVALIDA')
        garabatos = sum(1 for r in respuestas if r.respuesta_marcada == 'GARABATO')
        
        data.append({
            'Código Hoja': hoja.codigo_hoja,
            'Estado': hoja.estado,
            'API': hoja.api_utilizada,
            'Tiempo (s)': hoja.tiempo_procesamiento,
            'Válidas': validas,
            'Vacías': vacias,
            'Letra Inválida': invalidas,
            'Garabatos': garabatos,
            'Fecha': hoja.created_at.strftime('%d/%m/%Y %H:%M')
        })
    
    # Crear DataFrame
    df = pd.DataFrame(data)
    
    # Crear Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=resultados_postulando.xlsx'}
    )


@router.get("/verificar-codigos")
async def verificar_codigos(db: Session = Depends(get_db)):
    """Verifica códigos guardados en BD"""
    
    hojas = db.query(HojaRespuesta).filter_by(estado="generada").all()
    
    return {
        "total": len(hojas),
        "codigos": [
            {
                "id": h.id,
                "codigo_hoja": h.codigo_hoja,
                "postulante_id": h.postulante_id,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in hojas
        ]
    }