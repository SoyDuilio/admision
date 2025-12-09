"""
POSTULANDO - API de Captura de Hojas
VERSIÓN DEFINITIVA con validación de DNI manuscrito
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
    Procesamiento COMPLETO con validación de DNI manuscrito
    
    FLUJO:
    1. Guardar imagen
    2. Extraer código hoja + DNI manuscrito + respuestas (Vision API)
    3. Buscar hoja por código
    4. Validar DNI manuscrito vs postulante asignado
    5. Asociar/crear postulante según necesidad
    6. Guardar respuestas
    7. Calificar si hay gabarito
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
        
        print(f"✅ Código de hoja: {codigo_hoja}")
        print(f"✅ DNI manuscrito: {dni_manuscrito if dni_manuscrito else '(no detectado)'}")
        print(f"✅ Respuestas: {len(respuestas_array)}/100")
        
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
                    "icono": "🔍"
                }
            )
        
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
        
        print(f"✅ Hoja encontrada (ID: {hoja.id})")
        
        # ================================================================
        # 4. VALIDAR Y ASOCIAR POSTULANTE
        # ================================================================
        
        postulante_final = None
        alerta_discrepancia = None
        
        if dni_manuscrito:
            print(f"\n🔍 Validando DNI manuscrito: {dni_manuscrito}")
            
            # Buscar postulante por DNI manuscrito
            postulante_por_dni = db.query(Postulante).filter(
                Postulante.dni == dni_manuscrito
            ).first()
            
            if postulante_por_dni:
                print(f"  ✅ Postulante encontrado: {postulante_por_dni.nombres} {postulante_por_dni.apellido_paterno}")
                
                # Verificar si coincide con el pre-asignado
                if hoja.postulante_id and hoja.postulante_id != postulante_por_dni.id:
                    # DISCREPANCIA DETECTADA
                    postulante_asignado = db.query(Postulante).filter(
                        Postulante.id == hoja.postulante_id
                    ).first()
                    
                    alerta_discrepancia = {
                        "tipo": "discrepancia_dni",
                        "dni_manuscrito": dni_manuscrito,
                        "postulante_manuscrito": f"{postulante_por_dni.nombres} {postulante_por_dni.apellido_paterno}",
                        "dni_asignado": postulante_asignado.dni if postulante_asignado else None,
                        "postulante_asignado": f"{postulante_asignado.nombres} {postulante_asignado.apellido_paterno}" if postulante_asignado else None
                    }
                    
                    print(f"  ⚠️ DISCREPANCIA DETECTADA:")
                    print(f"     Hoja asignada a: {alerta_discrepancia['postulante_asignado']} (DNI: {alerta_discrepancia['dni_asignado']})")
                    print(f"     DNI manuscrito: {dni_manuscrito} ({alerta_discrepancia['postulante_manuscrito']})")
                    print(f"  ✅ Usando DNI manuscrito (tiene prioridad)")
                
                # Usar postulante detectado (prioridad)
                postulante_final = postulante_por_dni
                hoja.postulante_id = postulante_por_dni.id
                
            else:
                # DNI manuscrito NO existe en BD → Crear invitado
                print(f"  ⚠️ DNI {dni_manuscrito} no registrado")
                print(f"  📝 Creando postulante invitado...")
                
                postulante_invitado = Postulante(
                    dni=dni_manuscrito,
                    nombres="INVITADO",
                    apellido_paterno=f"DNI-{dni_manuscrito}",
                    apellido_materno="",
                    codigo_unico=f"INV-{dni_manuscrito}",
                    programa_educativo="INVITADO",
                    proceso_admision=hoja.proceso_admision,
                    tipo="invitado",  # ← Campo nuevo
                    activo=True,
                    examen_rendido=False
                )
                
                db.add(postulante_invitado)
                db.flush()
                
                postulante_final = postulante_invitado
                hoja.postulante_id = postulante_invitado.id
                
                alerta_discrepancia = {
                    "tipo": "postulante_invitado",
                    "dni_manuscrito": dni_manuscrito,
                    "mensaje": "Postulante no registrado - Creado como invitado"
                }
                
                print(f"  ✅ Invitado creado (ID: {postulante_invitado.id})")
        
        else:
            # DNI NO detectado
            print(f"\n⚠️ DNI manuscrito no detectado")
            
            if hoja.postulante_id:
                # Usar postulante pre-asignado
                postulante_final = db.query(Postulante).filter(
                    Postulante.id == hoja.postulante_id
                ).first()
                
                print(f"  ℹ️ Usando postulante pre-asignado: {postulante_final.nombres if postulante_final else 'N/A'}")
                
                alerta_discrepancia = {
                    "tipo": "dni_no_detectado",
                    "mensaje": "DNI manuscrito no se pudo leer - usando postulante pre-asignado"
                }
            else:
                # Sin DNI y sin pre-asignación → ERROR
                raise HTTPException(
                    status_code=400,
                    detail={
                        "titulo": "DNI NO DETECTADO",
                        "mensaje": "No se pudo leer el DNI manuscrito y la hoja no tiene postulante asignado.",
                        "icono": "❌"
                    }
                )
        
        # ================================================================
        # 5. REGISTRAR VALIDACIÓN DNI (para trazabilidad)
        # ================================================================
        
        if dni_manuscrito:
            validacion = ValidacionDNI(
                hoja_respuesta_id=hoja.id,
                dni=dni_manuscrito,
                estado="detectado" if not alerta_discrepancia else alerta_discrepancia["tipo"],
                fecha_captura=datetime.now()
            )
            db.add(validacion)
        
        # ================================================================
        # 6. ACTUALIZAR HOJA
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
        # 7. GUARDAR RESPUESTAS
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
        # 8. CALIFICAR SI HAY GABARITO
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
        # 9. MARCAR EXAMEN RENDIDO
        # ================================================================
        
        postulante_final.examen_rendido = True
        db.commit()
        
        # ================================================================
        # 10. RESPUESTA
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
                "api": "google_vision",
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