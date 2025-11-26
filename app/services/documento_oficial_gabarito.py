"""
POSTULANDO - Documento Oficial de Respuestas Correctas
app/api/documento_oficial.py

Endpoint para generar el documento oficial que se imprime, firma y lacra.
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import get_db
from app.models import ClaveRespuesta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/documento-oficial-gabarito", response_class=HTMLResponse)
async def documento_oficial_gabarito(
    request: Request,
    proceso: str = "2025-2",
    preview: bool = False,
    db: Session = Depends(get_db)
):
    """
    Genera el documento oficial de respuestas correctas para imprimir.
    
    IMPORTANTE: Este documento debe ser:
    1. Completado a mano por el equipo responsable
    2. Firmado por autoridades
    3. Lacrado en sobre
    4. Entregado al Director/Decano/Rector
    5. Abierto SOLO después de terminar el examen
    
    Parámetros:
    - proceso: Código del proceso de admisión
    - preview: Si es True, muestra ejemplo. Si es False, muestra formulario vacío
    """
    
    # Datos de ejemplo si preview=True
    if preview:
        ejemplo_data = {
            "proceso": proceso,
            "fecha_generacion": datetime.now().strftime("%d/%m/%Y"),
            "hora_generacion": datetime.now().strftime("%H:%M"),
            "respuestas_por_letra": {
                "A": {
                    "preguntas": [3, 5, 7, 12, 15, 18, 21, 24, 27, 30, 35, 38, 41, 46, 50, 55, 60],
                    "total": 17
                },
                "B": {
                    "preguntas": [2, 4, 6, 9, 11, 14, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 47, 52, 57, 62, 67, 72, 77],
                    "total": 23
                },
                "C": {
                    "preguntas": [1, 8, 10, 13, 17, 20, 23, 26, 29, 32, 36, 39, 44, 48, 51],
                    "total": 15
                },
                "D": {
                    "preguntas": [33, 42, 45, 49, 53, 54, 56, 58, 59, 61, 63, 64, 65, 66, 68, 69, 70, 71, 73, 74, 75, 76, 78, 79, 80],
                    "total": 25
                },
                "E": {
                    "preguntas": [81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100],
                    "total": 20
                }
            },
            "total_general": 100,
            "institucion": "Instituto Superior Tecnológico SANTANA",
            "proceso_nombre": "Examen de Admisión 2025-2",
            "es_preview": True
        }
    else:
        # Formulario en blanco para llenar a mano
        ejemplo_data = {
            "proceso": proceso,
            "fecha_generacion": datetime.now().strftime("%d/%m/%Y"),
            "hora_generacion": datetime.now().strftime("%H:%M"),
            "respuestas_por_letra": {
                "A": {"preguntas": [], "total": 0},
                "B": {"preguntas": [], "total": 0},
                "C": {"preguntas": [], "total": 0},
                "D": {"preguntas": [], "total": 0},
                "E": {"preguntas": [], "total": 0}
            },
            "total_general": 0,
            "institucion": "Instituto Superior Tecnológico SANTANA",
            "proceso_nombre": f"Examen de Admisión {proceso}",
            "es_preview": False
        }
    
    return templates.TemplateResponse(
        "documento_oficial_gabarito.html",
        {
            "request": request,
            **ejemplo_data
        }
    )


@router.get("/documento-oficial-gabarito-desde-bd")
async def documento_oficial_desde_bd(
    request: Request,
    proceso: str = "2025-2",
    db: Session = Depends(get_db)
):
    """
    Genera el documento oficial usando datos ya guardados en la BD.
    Útil para re-imprimir después de haber capturado el gabarito.
    """
    
    # Obtener todas las respuestas del proceso
    claves = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso
    ).order_by(ClaveRespuesta.numero_pregunta).all()
    
    if not claves:
        raise HTTPException(
            status_code=404,
            detail=f"No hay gabarito registrado para el proceso {proceso}"
        )
    
    # Organizar por letra
    respuestas_por_letra = {
        "A": {"preguntas": [], "total": 0},
        "B": {"preguntas": [], "total": 0},
        "C": {"preguntas": [], "total": 0},
        "D": {"preguntas": [], "total": 0},
        "E": {"preguntas": [], "total": 0}
    }
    
    for clave in claves:
        letra = clave.respuesta_correcta.upper()
        if letra in respuestas_por_letra:
            respuestas_por_letra[letra]["preguntas"].append(clave.numero_pregunta)
            respuestas_por_letra[letra]["total"] += 1
    
    # Ordenar preguntas
    for letra in respuestas_por_letra:
        respuestas_por_letra[letra]["preguntas"].sort()
    
    data = {
        "proceso": proceso,
        "fecha_generacion": datetime.now().strftime("%d/%m/%Y"),
        "hora_generacion": datetime.now().strftime("%H:%M"),
        "respuestas_por_letra": respuestas_por_letra,
        "total_general": len(claves),
        "institucion": "Instituto Superior Tecnológico SANTANA",
        "proceso_nombre": f"Examen de Admisión {proceso}",
        "es_preview": False
    }
    
    return templates.TemplateResponse(
        "documento_oficial_gabarito.html",
        {
            "request": request,
            **data
        }
    )