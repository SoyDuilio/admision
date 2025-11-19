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

from sqlalchemy import text, func
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

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
        from app.services.image_preprocessor_v2 import ImagePreprocessor
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



# ==================================
# API Gabarito - Endpoints Completos
# ==================================


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class GuardarGabaritoRequest(BaseModel):
    proceso: str
    respuestas: Dict[int, str]  # {1: 'A', 2: 'B', ..., 100: 'E'}


class GuardarGabaritoAgrupadoRequest(BaseModel):
    proceso: str
    respuestas_por_letra: Dict[str, List[int]]  # {'A': [1,5,10], 'B': [2,3], ...}


# ============================================================================
# ENDPOINT: GUARDAR GABARITO (FORMATO DICCIONARIO)
# ============================================================================

@router.post("/guardar-gabarito")
async def guardar_gabarito(
    data: GuardarGabaritoRequest,
    db: Session = Depends(get_db)
):
    """
    Guarda el gabarito en la base de datos.
    Llamado desde los 3 métodos: cámara, manual y voz.
    """
    try:
        # Validar 100 respuestas
        if len(data.respuestas) != 100:
            raise HTTPException(
                status_code=400,
                detail=f"Esperadas 100 respuestas, recibidas: {len(data.respuestas)}"
            )
        
        # Validar que estén del 1 al 100
        preguntas = set(data.respuestas.keys())
        esperadas = set(range(1, 101))
        
        if preguntas != esperadas:
            faltantes = esperadas - preguntas
            raise HTTPException(
                status_code=400,
                detail=f"Preguntas faltantes: {sorted(list(faltantes))[:10]}"
            )
        
        # Validar letras A-E
        letras_validas = {'A', 'B', 'C', 'D', 'E'}
        letras_invalidas = set(data.respuestas.values()) - letras_validas
        if letras_invalidas:
            raise HTTPException(
                status_code=400,
                detail=f"Letras inválidas: {letras_invalidas}"
            )
        
        # Limpiar gabarito anterior
        db.execute(
            text("DELETE FROM clave_respuestas WHERE proceso_admision = :proceso"),
            {"proceso": data.proceso}
        )
        
        # Insertar nuevo gabarito
        for numero, letra in data.respuestas.items():
            db.execute(text("""
                INSERT INTO clave_respuestas 
                    (numero_pregunta, respuesta_correcta, proceso_admision, created_at)
                VALUES 
                    (:num, :letra, :proceso, NOW())
            """), {
                "num": int(numero),
                "letra": letra.upper(),
                "proceso": data.proceso
            })
        
        db.commit()
        
        # Calificar automáticamente
        hojas_calificadas = 0
        try:
            result = db.execute(
                text("SELECT fn_calificar_todas_las_hojas(:proceso)"),
                {"proceso": data.proceso}
            )
            hojas_calificadas = result.scalar() or 0
            
            db.execute(
                text("SELECT fn_calcular_ranking(:proceso)"),
                {"proceso": data.proceso}
            )
            db.commit()
        except Exception as e:
            print(f"Error en calificación automática: {e}")
        
        # Contar distribución
        result = db.execute(text("""
            SELECT respuesta_correcta, COUNT(*) as cantidad
            FROM clave_respuestas
            WHERE proceso_admision = :proceso
            GROUP BY respuesta_correcta
            ORDER BY respuesta_correcta
        """), {"proceso": data.proceso})
        
        conteo = {row[0]: row[1] for row in result}
        
        return {
            "success": True,
            "message": "Gabarito guardado correctamente",
            "total_registrado": len(data.respuestas),
            "distribucion": conteo,
            "hojas_calificadas": hojas_calificadas,
            "proceso": data.proceso
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error al guardar gabarito: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT: GUARDAR GABARITO (FORMATO AGRUPADO)
# ============================================================================

@router.post("/guardar-gabarito-agrupado")
async def guardar_gabarito_agrupado(
    data: GuardarGabaritoAgrupadoRequest,
    db: Session = Depends(get_db)
):
    """
    Guarda el gabarito en formato agrupado por letra.
    
    Formato esperado:
    {
        "proceso": "2025-2",
        "respuestas_por_letra": {
            "A": [4, 10, 15, 20, ...],
            "B": [1, 6, 9, 14, ...],
            "C": [2, 7, 11, 16, ...],
            "D": [3, 8, 13, 18, ...],
            "E": [5, 12, 19, 24, ...]
        }
    }
    """
    
    try:
        # Convertir a formato diccionario
        respuestas_dict = {}
        
        for letra, preguntas in data.respuestas_por_letra.items():
            for num_pregunta in preguntas:
                if num_pregunta in respuestas_dict:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Pregunta {num_pregunta} duplicada"
                    )
                respuestas_dict[num_pregunta] = letra
        
        # Reutilizar el endpoint anterior
        request_data = GuardarGabaritoRequest(
            proceso=data.proceso,
            respuestas=respuestas_dict
        )
        
        return await guardar_gabarito(request_data, db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT: OBTENER GABARITO
# ============================================================================

@router.get("/obtener-gabarito/{proceso}")
async def obtener_gabarito(
    proceso: str,
    formato: str = "diccionario",  # "diccionario" o "agrupado"
    db: Session = Depends(get_db)
):
    """
    Obtiene el gabarito guardado.
    
    Parámetros:
    - formato: "diccionario" retorna {1: 'A', 2: 'B', ...}
    - formato: "agrupado" retorna {'A': [1,5,10], 'B': [2,3], ...}
    """
    
    try:
        query = text("""
            SELECT numero_pregunta, respuesta_correcta
            FROM clave_respuestas
            WHERE proceso_admision = :proceso
            ORDER BY numero_pregunta
        """)
        
        result = db.execute(query, {"proceso": proceso})
        rows = result.fetchall()
        
        if not rows:
            return {
                "success": False,
                "message": f"No hay gabarito registrado para el proceso {proceso}",
                "existe": False
            }
        
        if formato == "agrupado":
            # Formato agrupado por letra
            respuestas_agrupadas = {
                "A": [], "B": [], "C": [], "D": [], "E": []
            }
            
            for row in rows:
                letra = row.respuesta_correcta.upper()
                if letra in respuestas_agrupadas:
                    respuestas_agrupadas[letra].append(row.numero_pregunta)
            
            # Contar totales
            totales = {letra: len(preg) for letra, preg in respuestas_agrupadas.items()}
            
            return {
                "success": True,
                "existe": True,
                "proceso": proceso,
                "formato": "agrupado",
                "respuestas_por_letra": respuestas_agrupadas,
                "totales": totales,
                "total_general": len(rows)
            }
        
        else:
            # Formato diccionario
            respuestas_dict = {
                row.numero_pregunta: row.respuesta_correcta.upper()
                for row in rows
            }
            
            return {
                "success": True,
                "existe": True,
                "proceso": proceso,
                "formato": "diccionario",
                "respuestas": respuestas_dict,
                "total": len(respuestas_dict)
            }
        
    except Exception as e:
        print(f"Error al obtener gabarito: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINT: VERIFICAR SI EXISTE GABARITO
# ============================================================================

@router.get("/verificar-gabarito/{proceso}")
async def verificar_gabarito(
    proceso: str,
    db: Session = Depends(get_db)
):
    """
    Verifica si existe gabarito para un proceso.
    """
    
    try:
        query = text("""
            SELECT COUNT(*) as total
            FROM clave_respuestas
            WHERE proceso_admision = :proceso
        """)
        
        result = db.execute(query, {"proceso": proceso})
        total = result.scalar()
        
        return {
            "success": True,
            "existe": total > 0,
            "total_preguntas": total,
            "completo": total == 100,
            "proceso": proceso
        }
        
    except Exception as e:
        print(f"Error al verificar gabarito: {e}")
        raise HTTPException(status_code=500, detail=str(e))