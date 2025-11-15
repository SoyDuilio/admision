"""
POSTULANDO - API de Captura de Hojas
app/api/captura.py

Endpoints para procesar hojas capturadas con cámara.
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid
from datetime import datetime
import json

from app.database import get_db
from app.models import HojaRespuesta, Postulante, ClaveRespuesta, Calificacion

router = APIRouter()

# ============================================================================
# ENDPOINT PRINCIPAL DE CAPTURA
# ============================================================================

@router.post("/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    metadata_captura: str = Form(None),
    image_hash: str = Form(None),
    api: str = Form("auto"),
    db: Session = Depends(get_db)
):
    """
    Endpoint COMPLETO que:
    1. Guarda la imagen
    2. Extrae códigos y respuestas con Vision API
    3. BUSCA hoja existente por codigo_hoja
    4. ACTUALIZA registro en BD
    5. Guarda 100 respuestas
    6. Califica si existe gabarito
    7. Retorna resultado completo
    """
    
    from app.services.vision_service_v3 import (
        procesar_hoja_completa_v3,
        procesar_y_guardar_respuestas,
        calificar_hoja_con_gabarito
    )
    
    inicio = datetime.now()
    
    try:
        # ================================================================
        # 1. GUARDAR IMAGEN
        # ================================================================
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"hoja_{timestamp}_{unique_id}.jpg"
        
        uploads_dir = Path("uploads/hojas_originales")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = uploads_dir / filename
        
        with filepath.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        imagen_url = f"/uploads/hojas_originales/{filename}"
        
        print(f"\n{'='*70}")
        print(f"🚀 PROCESANDO HOJA DE RESPUESTAS")
        print(f"{'='*70}")
        print(f"📁 Archivo guardado: {filename}")
        
        # ================================================================
        # 2. PROCESAR CON VISION API
        # ================================================================
        
        print(f"\n🔍 Extrayendo datos con Vision API...")
        
        resultado_vision = await procesar_hoja_completa_v3(str(filepath))
        
        if not resultado_vision.get("success"):
            raise HTTPException(
                status_code=400,
                detail=resultado_vision.get('error', 'Error en Vision API')
            )
        
        datos_vision = resultado_vision.get("datos", {})
        respuestas_array = datos_vision.get("respuestas", [])
        
        # Validar 100 respuestas
        if len(respuestas_array) != 100:
            raise HTTPException(
                status_code=400,
                detail=f"❌ Se esperaban 100 respuestas, se detectaron {len(respuestas_array)}"
            )
        
        # Extraer código de hoja
        codigo_hoja = datos_vision.get("codigo_hoja")
        
        if not codigo_hoja:
            raise HTTPException(
                status_code=400,
                detail="❌ No se pudo detectar el código de hoja en la imagen. "
                       "Asegúrese de que el código esté visible y legible."
            )
        
        print(f"✅ Código de hoja detectado: {codigo_hoja}")
        print(f"✅ Respuestas detectadas: {len(respuestas_array)}/100")
        
        # ================================================================
        # 3. BUSCAR HOJA EXISTENTE
        # ================================================================
        
        print(f"\n🔍 Buscando hoja en base de datos...")
        
        hoja = db.query(HojaRespuesta).filter(
            HojaRespuesta.codigo_hoja == codigo_hoja
        ).first()
        
        if not hoja:
            raise HTTPException(
                status_code=404,
                detail={
                    "titulo": "HOJA NO ENCONTRADA",
                    "mensaje": f"El código '{codigo_hoja}' no existe en el sistema.",
                    "icono": "🔍",
                    "detalles": (
                        "Posibles causas:\n"
                        "• La hoja no fue generada/impresa desde el sistema\n"
                        "• El código fue leído incorrectamente\n"
                        "• Se generó una hoja nueva para este postulante\n\n"
                        "Solución: Genere e imprima la hoja desde el módulo correspondiente."
                    )
                }
            )
        
        # Validar estado
        if hoja.estado in ["procesado", "calificado"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "titulo": "HOJA YA PROCESADA",
                    "mensaje": f"Esta hoja ya fue escaneada anteriormente.",
                    "icono": "⚠️",
                    "detalles": (
                        f"Código: {codigo_hoja}\n"
                        f"Estado actual: {hoja.estado}\n"
                        f"Fecha de captura: {hoja.fecha_captura}\n\n"
                        "Si necesita reprocesarla, contacte al administrador."
                    )
                }
            )
        
        print(f"✅ Hoja encontrada:")
        print(f"   - ID: {hoja.id}")
        print(f"   - Código: {codigo_hoja}")
        print(f"   - Estado: {hoja.estado}")
        print(f"   - Postulante ID: {hoja.postulante_id}")
        
        # ================================================================
        # 4. OBTENER DATOS DEL POSTULANTE
        # ================================================================
        
        if not hoja.postulante_id:
            raise HTTPException(
                status_code=500,
                detail={
                    "titulo": "ERROR DE DATOS",
                    "mensaje": f"La hoja {codigo_hoja} no tiene postulante asociado.",
                    "icono": "❌",
                    "detalles": "Esto indica un problema en la generación de la hoja. Contacte al administrador."
                }
            )
        
        postulante = db.query(Postulante).filter(
            Postulante.id == hoja.postulante_id
        ).first()
        
        if not postulante:
            raise HTTPException(
                status_code=404,
                detail=f"❌ Postulante ID {hoja.postulante_id} no encontrado"
            )
        
        print(f"✅ Postulante:")
        print(f"   - DNI: {postulante.dni}")
        print(f"   - Nombre: {postulante.nombres} {postulante.apellido_paterno}")
        print(f"   - Programa: {postulante.programa_educativo}")
        
        # ================================================================
        # 5. ACTUALIZAR HOJA
        # ================================================================
        
        tiempo_procesamiento = (datetime.now() - inicio).total_seconds()
        
        # Metadata de captura
        metadata_dict = {}
        if metadata_captura:
            try:
                metadata_dict = json.loads(metadata_captura)
            except:
                metadata_dict = {}
        
        # Agregar info de procesamiento
        metadata_dict["vision_result"] = {
            "api": resultado_vision.get("api"),
            "modelo": resultado_vision.get("modelo"),
            "preprocessing": resultado_vision.get("preprocessing", {})
        }
        
        # Actualizar campos
        hoja.imagen_url = imagen_url
        hoja.imagen_original_nombre = file.filename
        hoja.estado = "procesado"
        hoja.api_utilizada = resultado_vision.get("api", "auto")
        hoja.tiempo_procesamiento = tiempo_procesamiento
        hoja.respuestas_detectadas = len(respuestas_array)
        hoja.metadata_json = json.dumps(metadata_dict)
        hoja.updated_at = datetime.now()
        
        db.flush()
        
        print(f"\n💾 Hoja actualizada correctamente")
        
        # ================================================================
        # 6. GUARDAR 100 RESPUESTAS
        # ================================================================
        
        print(f"\n💾 Guardando 100 respuestas individuales...")
        
        resultado_para_guardar = {
            "respuestas": respuestas_array
        }
        
        stats_guardado = await procesar_y_guardar_respuestas(
            hoja_respuesta_id=hoja.id,
            resultado_api=resultado_para_guardar,
            db=db
        )
        
        stats = stats_guardado.get("estadisticas", {})
        
        print(f"✅ Respuestas guardadas:")
        print(f"   - Válidas: {stats.get('validas', 0)}")
        print(f"   - Vacías: {stats.get('vacias', 0)}")
        print(f"   - Problemáticas: {stats.get('letra_invalida', 0) + stats.get('garabatos', 0)}")
        print(f"   - Requieren revisión: {stats.get('requieren_revision', 0)}")
        
        # ================================================================
        # 7. CALIFICAR SI EXISTE GABARITO
        # ================================================================
        
        # Buscar gabarito del proceso
        gabarito = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == hoja.proceso_admision
        ).first()
        
        # Si no hay gabarito del proceso específico, buscar el general
        if not gabarito:
            gabarito = db.query(ClaveRespuesta).filter(
                ClaveRespuesta.proceso_admision == "ADMISION_2025_2"
            ).first()
        
        calificacion_data = None
        
        if gabarito:
            print(f"\n📊 Calificando con gabarito: {gabarito.proceso_admision}")
            
            resultado_calificacion = await calificar_hoja_con_gabarito(
                hoja_respuesta_id=hoja.id,
                gabarito_id=gabarito.id,
                db=db
            )
            
            # Guardar/actualizar en tabla calificaciones
            calificacion_existente = db.query(Calificacion).filter(
                Calificacion.postulante_id == postulante.id
            ).first()
            
            if calificacion_existente:
                calificacion_existente.nota = resultado_calificacion["nota_final"]
                calificacion_existente.correctas = resultado_calificacion["correctas"]
                calificacion_existente.incorrectas = resultado_calificacion["incorrectas"]
                calificacion_existente.en_blanco = resultado_calificacion["no_calificables"]
                calificacion_existente.porcentaje_aciertos = resultado_calificacion["porcentaje"]
                calificacion_existente.aprobado = resultado_calificacion["nota_final"] >= 10.5
                calificacion_existente.calificado_at = datetime.now()
            else:
                calificacion = Calificacion(
                    postulante_id=postulante.id,
                    nota=int(resultado_calificacion["nota_final"]),
                    correctas=resultado_calificacion["correctas"],
                    incorrectas=resultado_calificacion["incorrectas"],
                    en_blanco=resultado_calificacion["no_calificables"],
                    no_legibles=0,
                    porcentaje_aciertos=resultado_calificacion["porcentaje"],
                    aprobado=resultado_calificacion["nota_final"] >= 10.5,
                    nota_minima=10,
                    created_at=datetime.now(),
                    calificado_at=datetime.now()
                )
                db.add(calificacion)
            
            db.commit()
            
            calificacion_data = {
                "nota": resultado_calificacion["nota_final"],
                "correctas": resultado_calificacion["correctas"],
                "incorrectas": resultado_calificacion["incorrectas"],
                "en_blanco": resultado_calificacion["no_calificables"],
                "porcentaje": resultado_calificacion["porcentaje"],
                "aprobado": resultado_calificacion["nota_final"] >= 10.5
            }
            
            print(f"✅ Calificación completada:")
            print(f"   - Nota: {calificacion_data['nota']}/20")
            print(f"   - Correctas: {calificacion_data['correctas']}/100")
            print(f"   - Estado: {'APROBADO ✅' if calificacion_data['aprobado'] else 'DESAPROBADO ❌'}")
        else:
            print(f"\n⚠️ No hay gabarito disponible - hoja procesada sin calificar")
            db.commit()
        
        # ================================================================
        # 8. MARCAR EXAMEN COMO RENDIDO
        # ================================================================
        
        postulante.examen_rendido = True
        db.commit()
        
        # ================================================================
        # 9. PREPARAR RESPUESTA
        # ================================================================
        
        print(f"\n{'='*70}")
        print(f"✅ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        print(f"{'='*70}")
        print(f"⏱️  Tiempo total: {tiempo_procesamiento:.2f}s")
        print(f"🎯 API utilizada: {resultado_vision.get('api', 'auto').upper()}")
        print(f"📋 Hoja ID: {hoja.id}")
        print(f"👤 Postulante: {postulante.dni}\n")
        
        return {
            "success": True,
            "message": "Hoja procesada y calificada exitosamente",
            
            # Datos de la hoja
            "hoja_respuesta_id": hoja.id,
            "codigo_hoja": codigo_hoja,
            
            # Postulante
            "postulante": {
                "id": postulante.id,
                "dni": postulante.dni,
                "nombres": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa": postulante.programa_educativo
            },
            
            # Procesamiento
            "procesamiento": {
                "api": resultado_vision.get("api"),
                "modelo": resultado_vision.get("modelo"),
                "tiempo": round(tiempo_procesamiento, 2)
            },
            
            # Respuestas
            "respuestas_detectadas": len(respuestas_array),
            "detalle": {
                "total_respuestas": 100,
                "validas": stats.get("validas", 0),
                "vacias": stats.get("vacias", 0),
                "problematicas": (
                    stats.get("letra_invalida", 0) + 
                    stats.get("garabatos", 0) + 
                    stats.get("multiple", 0) + 
                    stats.get("ilegible", 0)
                )
            },
            
            # Calificación
            "calificacion": calificacion_data
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        db.rollback()
        
        import traceback
        error_detail = traceback.format_exc()
        
        print(f"\n{'='*70}")
        print(f"❌ ERROR EN PROCESAMIENTO")
        print(f"{'='*70}")
        print(error_detail)
        print(f"{'='*70}\n")
        
        return {
            "success": False,
            "error": {
                "titulo": "Error en Procesamiento",
                "mensaje": str(e),
                "icono": "❌",
                "detalles_tecnicos": error_detail
            }
        }


@router.put("/hoja/{hoja_id}/marcar-revision")
async def marcar_hoja_revision(
    hoja_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Marca una hoja para revisión manual después de validación del operador.
    """
    
    requiere_revision_manual = data.get('requiere_revision_manual')
    observacion = data.get('observacion')
    
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        raise HTTPException(status_code=404, detail="Hoja no encontrada")
    
    # Actualizar metadata
    metadata = hoja.metadata_json or {}
    metadata['requiere_revision_manual'] = requiere_revision_manual
    metadata['observacion_operador'] = observacion
    metadata['marcado_revision_at'] = datetime.now().isoformat()
    
    hoja.metadata_json = metadata
    
    db.commit()
    
    return {
        "success": True,
        "message": "Hoja marcada para revisión" if requiere_revision_manual else "Hoja marcada como OK"
    }