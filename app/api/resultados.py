"""
POSTULANDO - API de Resultados y Estadísticas
app/api/resultados.py

Endpoints para consultar resultados, rankings y exportar datos.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
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


@router.get("/hoja/{hoja_id}/detalle")
async def obtener_detalle_hoja(
    hoja_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene el detalle completo de una hoja de respuestas.
    """
    
    try:
        # Obtener hoja
        query_hoja = text("""
            SELECT 
                hr.id,
                hr.codigo_hoja,
                hr.postulante_id,
                hr.codigo_aula,
                hr.estado,
                hr.api_utilizada,
                hr.tiempo_procesamiento,
                hr.fecha_captura,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                p.codigo_unico,
                p.dni,
                hr.nota_final,
                hr.respuestas_correctas_count,
                hr.proceso_admision
            FROM hojas_respuestas hr
            LEFT JOIN postulantes p ON hr.postulante_id = p.id
            WHERE hr.id = :hoja_id
        """)
        
        result = db.execute(query_hoja, {"hoja_id": hoja_id})
        hoja_row = result.fetchone()
        
        if not hoja_row:
            raise HTTPException(status_code=404, detail="Hoja no encontrada")
        
        # Obtener las 100 respuestas
        query_respuestas = text("""
            SELECT 
                r.numero_pregunta,
                r.respuesta_marcada,
                r.confianza,
                r.es_correcta,
                r.requiere_revision,
                r.observacion,
                cr.respuesta_correcta,
                CASE 
                    WHEN r.es_correcta = TRUE THEN 'CORRECTA'
                    WHEN r.es_correcta = FALSE AND r.respuesta_marcada IN ('A','B','C','D','E') THEN 'INCORRECTA'
                    WHEN r.respuesta_marcada = 'VACIO' THEN 'VACIA'
                    WHEN r.respuesta_marcada IN ('LETRA_INVALIDA', 'GARABATO', 'MULTIPLE') THEN 'INVALIDA'
                    WHEN r.requiere_revision = TRUE THEN 'INVALIDA'
                    ELSE 'SIN_CALIFICAR'
                END as resultado
            FROM respuestas r
            LEFT JOIN clave_respuestas cr 
                ON r.numero_pregunta = cr.numero_pregunta 
                AND cr.proceso_admision = :proceso
            WHERE r.hoja_respuesta_id = :hoja_id
            ORDER BY r.numero_pregunta
        """)
        
        proceso = hoja_row[15] or 'ADMISION_2025_2'
        
        result_resp = db.execute(query_respuestas, {
            "hoja_id": hoja_id,
            "proceso": proceso
        })
        respuestas_rows = result_resp.fetchall()
        
        # Formatear respuestas
        respuestas = []
        for row in respuestas_rows:
            respuestas.append({
                "numero": row[0],
                "marcada": row[1],
                "confianza": float(row[2]) if row[2] else 0.0,
                "es_correcta": row[3],
                "requiere_revision": row[4],
                "observacion": row[5],
                "correcta": row[6],
                "resultado": row[7]
            })
        
        # Calcular estadísticas
        stats = {
            "correctas": sum(1 for r in respuestas if r["resultado"] == "CORRECTA"),
            "incorrectas": sum(1 for r in respuestas if r["resultado"] == "INCORRECTA"),
            "vacias": sum(1 for r in respuestas if r["resultado"] == "VACIA"),
            "invalidas": sum(1 for r in respuestas if r["resultado"] == "INVALIDA"),
            "sin_calificar": sum(1 for r in respuestas if r["resultado"] == "SIN_CALIFICAR")
        }
        
        # Construir nombre completo del postulante
        apellidos = ""
        if hoja_row[9]:  # apellido_paterno
            apellidos += hoja_row[9]
        if hoja_row[10]:  # apellido_materno
            apellidos += " " + hoja_row[10]
        apellidos = apellidos.strip()
        
        return {
            "success": True,
            "hoja": {
                "id": hoja_row[0],
                "codigo": hoja_row[1],
                "postulante_id": hoja_row[2],
                "aula": hoja_row[3],
                "estado": hoja_row[4],
                "api": hoja_row[5],
                "tiempo": float(hoja_row[6]) if hoja_row[6] else 0,
                "fecha": hoja_row[7].strftime("%d/%m/%Y %H:%M") if hoja_row[7] else None,
                "postulante": {
                    "nombres": hoja_row[8],
                    "apellidos": apellidos,
                    "codigo": hoja_row[11],
                    "dni": hoja_row[12]
                } if hoja_row[8] else None,
                "calificacion": {
                    "puntaje": float(hoja_row[13]) if hoja_row[13] else None,
                    "correctas": hoja_row[14],
                    "incorrectas": len(respuestas) - hoja_row[14] if hoja_row[14] else None,
                    "vacias": stats["vacias"],
                    "puesto": None
                } if hoja_row[13] is not None else None
            },
            "respuestas": respuestas,
            "estadisticas": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener detalle: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))