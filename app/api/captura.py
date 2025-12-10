"""
POSTULANDO - API de Captura de Hojas
VERSIÓN PILOTO - Sin validación de código de hoja
Solo se valida DNI manuscrito
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
import shutil
import uuid
from datetime import datetime
import json

from app.database import get_db
from app.models import HojaRespuesta, Postulante, ClaveRespuesta, Calificacion, ValidacionDNI

router = APIRouter()


@router.post("/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    metadata_captura: str = Form(None),
    image_hash: str = Form(None),
    api: str = Form("auto"),
    db: Session = Depends(get_db)
):
    """
    Procesamiento COMPLETO - VERSIÓN PILOTO
    
    CAMBIO PRINCIPAL:
    - NO valida si código de hoja existe en BD
    - Crea hoja automáticamente si no existe
    - Solo requiere DNI manuscrito válido
    
    FLUJO:
    1. Guardar imagen
    2. Extraer código hoja + DNI manuscrito + respuestas (Gemini)
    3. Buscar/crear postulante por DNI
    4. Buscar/crear hoja por código
    5. Guardar respuestas
    6. Calificar si hay gabarito
    """
    
    from app.services.vision_service_v3_simple import (
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
        # 2. PROCESAR CON GEMINI 2.5 FLASH
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
        codigo_hoja = datos_vision.get("codigo_hoja")
        dni_manuscrito = datos_vision.get("dni_postulante", "")
        
        # Validaciones básicas
        if len(respuestas_array) != 100:
            raise HTTPException(
                status_code=400,
                detail=f"❌ Se esperaban 100 respuestas, se detectaron {len(respuestas_array)}"
            )
        
        if not codigo_hoja:
            raise HTTPException(
                status_code=400,
                detail="❌ No se detectó código de hoja"
            )
        
        if not dni_manuscrito:
            raise HTTPException(
                status_code=400,
                detail={
                    "titulo": "DNI NO DETECTADO",
                    "mensaje": "No se pudo leer el DNI manuscrito.",
                    "icono": "❌",
                    "sugerencia": "Verifica que el DNI esté escrito claramente en los 8 rectángulos."
                }
            )
        
        print(f"✅ Código de hoja: {codigo_hoja}")
        print(f"✅ DNI manuscrito: {dni_manuscrito}")
        print(f"✅ Respuestas: {len(respuestas_array)}/100")
        
        # ================================================================
        # 3. BUSCAR O CREAR HOJA (SIN VALIDAR CÓDIGO)
        # ================================================================
        
        print(f"\n📋 Modo piloto: Creando hoja automática...")
        
        # Verificar si ya existe una hoja con este DNI en estado completado
        query_hoja_existente = text("""
            SELECT h.id, h.codigo_hoja, h.estado, h.fecha_captura,
                   p.nombres, p.apellido_paterno, p.apellido_materno
            FROM hojas_respuestas h
            JOIN postulantes p ON h.postulante_id = p.id
            WHERE p.dni = :dni 
              AND h.proceso_admision = :proceso
              AND h.estado = 'completado'
            ORDER BY h.fecha_captura DESC
            LIMIT 1
        """)
        
        hoja_duplicada = db.execute(query_hoja_existente, {
            "dni": dni_manuscrito,
            "proceso": "2025-2"
        }).fetchone()
        
        if hoja_duplicada:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "HOJA_YA_CAPTURADA",
                    "titulo": "⚠️ HOJA YA CAPTURADA",
                    "mensaje": f"El DNI {dni_manuscrito} ya tiene una hoja procesada.",
                    "postulante": f"{hoja_duplicada.nombres} {hoja_duplicada.apellido_paterno} {hoja_duplicada.apellido_materno}",
                    "codigo_anterior": hoja_duplicada.codigo_hoja,
                    "fecha_captura": str(hoja_duplicada.fecha_captura),
                    "sugerencia": "Esta hoja ya fue capturada anteriormente. No se puede volver a capturar."
                }
            )
        
        # Buscar o crear postulante
        postulante = db.query(Postulante).filter(
            Postulante.dni == dni_manuscrito
        ).first()
        
        if not postulante:
            # Crear postulante invitado
            print(f"  📝 Creando postulante invitado para DNI {dni_manuscrito}...")
            
            postulante = Postulante(
                dni=dni_manuscrito,
                nombres="INVITADO",
                apellido_paterno=f"DNI-{dni_manuscrito}",
                apellido_materno="",
                codigo_unico=f"INV-{dni_manuscrito}",
                programa_educativo="INVITADO",
                proceso_admision="2025-2",
                tipo="invitado",
                activo=True,
                examen_rendido=False
            )
            
            db.add(postulante)
            db.flush()
            
            print(f"  ✅ Invitado creado (ID: {postulante.id})")
        else:
            print(f"  ✅ Postulante encontrado: {postulante.nombres} {postulante.apellido_paterno}")
        
        # Buscar hoja por código
        hoja = db.query(HojaRespuesta).filter(
            HojaRespuesta.codigo_hoja == codigo_hoja
        ).first()
        
        if not hoja:
            # Crear hoja temporal
            print(f"  📄 Creando hoja temporal con código {codigo_hoja}...")
            
            # Obtener último orden_aula
            query_max_orden = text("""
                SELECT COALESCE(MAX(orden_aula), 0) 
                FROM hojas_respuestas
                WHERE proceso_admision = :proceso
            """)
            max_orden = db.execute(query_max_orden, {"proceso": "2025-2"}).scalar()
            nuevo_orden = max_orden + 1
            
            hoja = HojaRespuesta(
                codigo_hoja=codigo_hoja,
                postulante_id=postulante.id,
                proceso_admision="2025-2",
                orden_aula=nuevo_orden,
                codigo_aula="PILOTO",
                dni_profesor="00000000",
                estado="generada",
                respuestas_detectadas=0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.add(hoja)
            db.flush()
            
            print(f"  ✅ Hoja creada (ID: {hoja.id}, Orden: {nuevo_orden})")
        else:
            # Hoja existe
            print(f"  ✅ Hoja encontrada (ID: {hoja.id})")
            
            # Validar estado
            if hoja.estado in ["completado", "calificado"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "titulo": "HOJA YA PROCESADA",
                        "mensaje": f"Esta hoja ya fue procesada anteriormente.",
                        "icono": "⚠️",
                        "detalles": (
                            f"Código: {codigo_hoja}\n"
                            f"Estado: {hoja.estado}\n"
                            f"Fecha captura: {hoja.fecha_captura}"
                        )
                    }
                )
            
            # Actualizar postulante si es diferente
            if hoja.postulante_id != postulante.id:
                print(f"  ⚠️ Actualizando postulante de hoja...")
                hoja.postulante_id = postulante.id
        
        postulante_final = postulante
        alerta_discrepancia = None
        
        # ================================================================
        # 4. REGISTRAR VALIDACIÓN DNI (para trazabilidad)
        # ================================================================
        
        validacion = ValidacionDNI(
            hoja_respuesta_id=hoja.id,
            dni=dni_manuscrito,
            estado="detectado",
            fecha_captura=datetime.now()
        )
        db.add(validacion)
        
        # ================================================================
        # 5. ACTUALIZAR HOJA
        # ================================================================
        
        tiempo_procesamiento = (datetime.now() - inicio).total_seconds()
        
        metadata_dict = {}
        if metadata_captura:
            try:
                metadata_dict = json.loads(metadata_captura)
            except:
                pass
        
        metadata_dict["vision_result"] = {
            "api": resultado_vision.get("api"),
            "modelo": resultado_vision.get("modelo"),
            "dni_manuscrito_detectado": dni_manuscrito,
            "alerta": alerta_discrepancia
        }
        
        hoja.imagen_url = imagen_url
        hoja.imagen_original_nombre = file.filename
        hoja.estado = "completado"
        hoja.fecha_captura = datetime.now()
        hoja.api_utilizada = "google"
        hoja.tiempo_procesamiento = tiempo_procesamiento
        hoja.respuestas_detectadas = len(respuestas_array)
        hoja.metadata_json = json.dumps(metadata_dict)
        hoja.updated_at = datetime.now()
        
        db.flush()
        
        print(f"\n💾 Hoja actualizada")
        print(f"   Postulante final: {postulante_final.dni} - {postulante_final.nombres} {postulante_final.apellido_paterno}")
        
        # ================================================================
        # 6. GUARDAR RESPUESTAS
        # ================================================================
        
        print(f"\n💾 Guardando 100 respuestas...")
        
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
        print(f"   Válidas: {stats.get('validas', 0)}")
        print(f"   Vacías: {stats.get('vacias', 0)}")
        
        # ================================================================
        # 7. CALIFICAR SI HAY GABARITO
        # ================================================================
        
        gabarito = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == hoja.proceso_admision
        ).first()
        
        calificacion_data = None
        
        if gabarito:
            print(f"\n📊 Calificando con gabarito...")
            
            resultado_calificacion = await calificar_hoja_con_gabarito(
                hoja_respuesta_id=hoja.id,
                gabarito_id=gabarito.id,
                db=db
            )
            
            # Guardar calificación
            calificacion_existente = db.query(Calificacion).filter(
                Calificacion.postulante_id == postulante_final.id
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
                    postulante_id=postulante_final.id,
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
            
            calificacion_data = {
                "nota": resultado_calificacion["nota_final"],
                "correctas": resultado_calificacion["correctas"],
                "incorrectas": resultado_calificacion["incorrectas"],
                "en_blanco": resultado_calificacion["no_calificables"],
                "porcentaje": resultado_calificacion["porcentaje"],
                "aprobado": resultado_calificacion["nota_final"] >= 10.5
            }
            
            print(f"✅ Nota: {calificacion_data['nota']}/20")
        
        # ================================================================
        # 8. MARCAR EXAMEN RENDIDO
        # ================================================================
        
        postulante_final.examen_rendido = True
        db.commit()
        
        # ================================================================
        # 9. RESPUESTA
        # ================================================================
        
        print(f"\n{'='*70}")
        print(f"✅ PROCESAMIENTO COMPLETADO")
        print(f"{'='*70}\n")
        
        respuesta_final = {
            "success": True,
            "message": "Hoja procesada exitosamente",
            "hoja_respuesta_id": hoja.id,
            "codigo_hoja": codigo_hoja,
            "postulante": {
                "id": postulante_final.id,
                "dni": postulante_final.dni,
                "nombres": f"{postulante_final.apellido_paterno} {postulante_final.apellido_materno}, {postulante_final.nombres}",
                "programa": postulante_final.programa_educativo,
                "tipo": getattr(postulante_final, 'tipo', 'regular')
            },
            "procesamiento": {
                "api": "gemini-2.5-flash",
                "tiempo": round(tiempo_procesamiento, 2),
                "dni_detectado": bool(dni_manuscrito)
            },
            "respuestas_detectadas": len(respuestas_array),
            "detalle": stats,
            "calificacion": calificacion_data
        }
        
        # Agregar alerta si existe
        if alerta_discrepancia:
            respuesta_final["alerta"] = alerta_discrepancia
        
        return respuesta_final
        
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