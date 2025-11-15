"""
POSTULANDO - API de Gabarito
app/api/gabarito.py

Endpoints para registrar, editar y consultar gabaritos (claves de respuesta).
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
from collections import Counter
import json
import shutil

from app.database import get_db
from app.models import ClaveRespuesta

router = APIRouter()

# ============================================================================
# ENDPOINTS DE GABARITO
# ============================================================================

@router.post("/registrar-gabarito-manual")
async def registrar_gabarito_manual(
    respuestas: str = Form(...),
    proceso_admision: str = Form("2025-2"),
    db: Session = Depends(get_db)
):
    """Registra las respuestas correctas manualmente"""
    
    try:
        # Convertir a lista
        lista_respuestas = [r.strip().upper() for r in respuestas.split(",")]
        
        if len(lista_respuestas) != 100:
            raise HTTPException(
                status_code=400,
                detail=f"Se esperan 100 respuestas, se recibieron {len(lista_respuestas)}"
            )
        
        # Validar
        validas = set(['A', 'B', 'C', 'D', 'E'])
        for i, resp in enumerate(lista_respuestas, 1):
            if resp not in validas:
                raise HTTPException(
                    status_code=400,
                    detail=f"Respuesta {i} inválida: '{resp}'"
                )
        
        # Borrar anterior
        db.query(ClaveRespuesta).filter_by(proceso_admision=proceso_admision).delete()
        
        # Insertar
        for i, respuesta in enumerate(lista_respuestas, 1):
            cr = ClaveRespuesta(
                numero_pregunta=i,
                respuesta_correcta=respuesta,
                proceso_admision=proceso_admision
            )
            db.add(cr)
        
        db.commit()
        
        return {
            "success": True,
            "mensaje": "Gabarito registrado exitosamente",
            "proceso": proceso_admision,
            "total_respuestas": len(lista_respuestas)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gabarito/procesar-manual")
async def procesar_gabarito_manual(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Procesa respuestas del formulario manual.
    Genera estadísticas por columna y general.
    Retorna data para confirmación.
    """
    
    respuestas = data.get('respuestas', {})
    proceso = data.get('proceso', 'ADMISION_2025_2')
    
    # Validar que sean exactamente 100 respuestas
    if len(respuestas) != 100:
        raise HTTPException(
            status_code=400, 
            detail=f"Se esperan 100 respuestas, recibidas: {len(respuestas)}"
        )
    
    # Validar que todas sean A, B, C, D o E
    respuestas_validas = {'A', 'B', 'C', 'D', 'E'}
    for num, resp in respuestas.items():
        if resp.upper() not in respuestas_validas:
            raise HTTPException(
                status_code=400,
                detail=f"Pregunta {num}: respuesta inválida '{resp}'. Solo se permiten A, B, C, D, E"
            )
    
    # Convertir a mayúsculas
    respuestas_upper = {k: v.upper() for k, v in respuestas.items()}
    
    # Calcular estadísticas por columna (5 columnas x 20 filas)
    estadisticas_columnas = []
    
    for col in range(5):  # 5 columnas
        inicio = col * 20 + 1
        fin = inicio + 20
        
        respuestas_columna = [
            respuestas_upper[str(i)] 
            for i in range(inicio, fin)
        ]
        
        conteo = Counter(respuestas_columna)
        
        estadisticas_columnas.append({
            'columna': col + 1,
            'inicio': inicio,
            'fin': fin - 1,
            'conteo': {
                'A': conteo.get('A', 0),
                'B': conteo.get('B', 0),
                'C': conteo.get('C', 0),
                'D': conteo.get('D', 0),
                'E': conteo.get('E', 0)
            }
        })
    
    # Resumen general
    todas_respuestas = list(respuestas_upper.values())
    conteo_general = Counter(todas_respuestas)
    
    resumen_general = {
        'A': conteo_general.get('A', 0),
        'B': conteo_general.get('B', 0),
        'C': conteo_general.get('C', 0),
        'D': conteo_general.get('D', 0),
        'E': conteo_general.get('E', 0),
        'total': 100
    }
    
    return {
        "success": True,
        "proceso": proceso,
        "respuestas": respuestas_upper,
        "estadisticas_columnas": estadisticas_columnas,
        "resumen_general": resumen_general,
        "message": "Gabarito procesado. Revise las estadísticas antes de confirmar."
    }


@router.post("/gabarito/procesar-imagen")
async def procesar_gabarito_imagen(
    file: UploadFile = File(...),
    api: str = Form("google"),
    proceso: str = Form("ADMISION_2025_2"),
    db: Session = Depends(get_db)
):
    """
    Procesa imagen de gabarito capturada con cámara.
    Usa el mismo sistema de visión que para hojas de postulantes.
    """
    
    try:
        # Guardar temporal
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gabarito_{timestamp}.jpg"
        temp_path = Path("temp_uploads") / filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Pre-procesar con OpenCV
        from app.services.image_preprocessor import ImagePreprocessor
        preprocessor = ImagePreprocessor()
        processed_path = preprocessor.preprocess_image(str(temp_path))
        
        # Procesar con Vision API
        from app.services.vision_service_v2 import procesar_hoja_con_vision_api
        
        with open(processed_path, "rb") as f:
            image_bytes = f.read()
        
        resultado_api = await procesar_hoja_con_vision_api(
            image_bytes,
            api_service=api,
            use_opencv=True
        )
        
        if not resultado_api.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Error al procesar imagen: {resultado_api.get('error')}"
            )
        
        # Extraer respuestas del JSON
        respuestas_raw = resultado_api.get("data", {}).get("respuestas", [])
        
        # Convertir a diccionario {numero: respuesta}
        respuestas_dict = {}
        for resp in respuestas_raw:
            numero = str(resp.get("numero"))
            respuesta = resp.get("respuesta", "").upper()
            
            # Solo tomar respuestas válidas (A-E)
            if respuesta in ['A', 'B', 'C', 'D', 'E']:
                respuestas_dict[numero] = respuesta
        
        # Validar que se detectaron 100 respuestas válidas
        if len(respuestas_dict) != 100:
            return {
                "success": False,
                "error": f"Solo se detectaron {len(respuestas_dict)} respuestas válidas. Se esperan 100.",
                "respuestas_detectadas": len(respuestas_dict),
                "respuestas": respuestas_dict,
                "mensaje": "Por favor, revise la imagen y complete manualmente las respuestas faltantes."
            }
        
        # Procesar igual que formulario manual
        return await procesar_gabarito_manual(
            data={"respuestas": respuestas_dict, "proceso": proceso},
            db=db
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar imagen: {str(e)}"
        )
    finally:
        # Limpiar temporales
        if temp_path.exists():
            temp_path.unlink()


@router.post("/gabarito/confirmar")
async def confirmar_gabarito(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Guarda el gabarito confirmado en la base de datos.
    """
    
    proceso = data.get('proceso')
    respuestas = data.get('respuestas', {})
    nombre = data.get('nombre')
    observaciones = data.get('observaciones')
    
    # Verificar si ya existe gabarito para este proceso
    existe = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso
    ).first()
    
    if existe:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un gabarito para el proceso {proceso}. Use la opción de editar."
        )
    
    # Crear gabarito
    gabarito = ClaveRespuesta(
        proceso_admision=proceso,
        nombre=nombre or f"Gabarito {proceso}",
        respuestas_json=json.dumps(respuestas),
        observaciones=observaciones
    )
    
    db.add(gabarito)
    db.commit()
    db.refresh(gabarito)
    
    # TODO: Implementar tabla respuestas_correctas si es necesaria
    # Por ahora solo usamos ClaveRespuesta con JSON
    
    return {
        "success": True,
        "gabarito_id": gabarito.id,
        "proceso": proceso,
        "total_respuestas": len(respuestas),
        "message": "Gabarito guardado correctamente"
    }


@router.get("/gabarito/{proceso}")
async def obtener_gabarito(
    proceso: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el gabarito de un proceso específico.
    """
    
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso
    ).first()
    
    if not gabarito:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró gabarito para el proceso {proceso}"
        )
    
    respuestas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
    
    return {
        "id": gabarito.id,
        "proceso": gabarito.proceso_admision,
        "nombre": gabarito.nombre,
        "respuestas": respuestas,
        "observaciones": gabarito.observaciones,
        "fecha_creacion": gabarito.created_at.isoformat()
    }


@router.put("/gabarito/{gabarito_id}/editar")
async def editar_gabarito(
    gabarito_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Permite editar un gabarito existente.
    """
    
    respuestas = data.get('respuestas', {})
    observaciones = data.get('observaciones')
    
    gabarito = db.query(ClaveRespuesta).filter(ClaveRespuesta.id == gabarito_id).first()
    
    if not gabarito:
        raise HTTPException(status_code=404, detail="Gabarito no encontrado")
    
    # Actualizar
    gabarito.respuestas_json = json.dumps(respuestas)
    gabarito.observaciones = observaciones
    gabarito.updated_at = datetime.now()
    
    # TODO: Actualizar tabla respuestas_correctas si existe
    
    db.commit()
    
    return {
        "success": True,
        "message": "Gabarito actualizado correctamente"
    }