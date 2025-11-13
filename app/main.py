"""
POSTULANDO - Sistema de Exámenes de Admisión
main.py LIMPIO Y MODULARIZADO
"""

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from typing import Optional, List
from io import BytesIO
import zipfile
from datetime import datetime, timezone
import tempfile
import os
import json
import time
import shutil

# Imports locales
from app.database import SessionLocal, engine, Base
from app.models import (
    Postulante, HojaRespuesta, ClaveRespuesta, 
    Calificacion, Profesor, Aula, Respuesta
)
from app.config import settings

# Servicios modularizados
from app.services import (
    generar_hoja_respuestas_pdf,
    procesar_con_api_seleccionada,
    validar_codigos,
    calcular_calificacion,
    gabarito_existe
)
from app.utils import (
    generar_codigo_hoja_unico,
    guardar_foto_temporal,
    crear_directorio_capturas,
    crear_directorio_generadas
)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Inicializar FastAPI
app = FastAPI(
    title="POSTULANDO",
    description="Sistema de Exámenes de Admisión con Vision AI",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def obtener_estadisticas():
    """Obtiene estadísticas generales del sistema"""
    db = SessionLocal()
    try:
        total_postulantes = db.query(func.count(Postulante.id)).scalar() or 0
        hojas_procesadas = db.query(func.count(HojaRespuesta.id)).scalar() or 0
        respuestas_correctas = db.query(func.count(ClaveRespuesta.id)).scalar() or 0
        calificados = db.query(func.count(Calificacion.id)).scalar() or 0
        
        return {
            "total_postulantes": total_postulantes,
            "hojas_procesadas": hojas_procesadas,
            "gabarito_cargado": respuestas_correctas == 100,
            "respuestas_correctas": respuestas_correctas,
            "calificados": calificados
        }
    finally:
        db.close()


# ============================================================================
# RUTAS DE PÁGINAS
# ============================================================================

@app.get("/")
async def index(request: Request):
    """Página principal - Dashboard"""
    stats = obtener_estadisticas()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats
    })


@app.get("/generar-hojas")
async def generar_hojas_page(request: Request):
    """Página para generar hojas de respuestas"""
    db = SessionLocal()
    try:
        postulantes = db.query(Postulante).order_by(Postulante.id).all()
        return templates.TemplateResponse("generar_hojas.html", {
            "request": request,
            "total_postulantes": len(postulantes),
            "postulantes": postulantes
        })
    finally:
        db.close()


@app.get("/capturar-hojas")
async def capturar_hojas_page(request: Request):
    """Página para capturar hojas con cámara"""
    db = SessionLocal()
    try:
        total_postulantes = db.query(func.count(Postulante.id)).scalar() or 0
        hojas_procesadas = db.query(func.count(HojaRespuesta.id)).scalar() or 0
        
        return templates.TemplateResponse("capturar_hojas.html", {
            "request": request,
            "total_postulantes": total_postulantes,
            "hojas_procesadas": hojas_procesadas
        })
    finally:
        db.close()


@app.get("/registrar-gabarito")
async def registrar_gabarito_page(request: Request):
    """Página para registrar respuestas correctas"""
    db = SessionLocal()
    try:
        gabarito_existe_flag = db.query(func.count(ClaveRespuesta.id)).scalar() > 0
        
        return templates.TemplateResponse("registrar_gabarito.html", {
            "request": request,
            "gabarito_ya_existe": gabarito_existe_flag
        })
    finally:
        db.close()


@app.get("/resultados")
async def resultados_page(request: Request):
    """Página de resultados"""
    return {
        "message": "Página de resultados en construcción",
        "status": "coming_soon"
    }


@app.get("/health")
async def health_check():
    """Endpoint para verificar que el sistema funciona"""
    stats = obtener_estadisticas()
    return {
        "status": "ok",
        "message": "POSTULANDO funcionando correctamente",
        "stats": stats
    }


# ============================================================================
# ENDPOINT: GENERAR HOJAS CON CÓDIGOS PRE-IMPRESOS
# ============================================================================

@app.post("/api/generar-hojas-examen")
async def generar_hojas_examen(
    proceso_admision: str = "2025-2",
    cantidad: int = None,
    postulantes_ids: list = None,
    codigo_aula: str = "A101",
    dni_profesor: str = "00000000"
):
    """
    Genera hojas de respuestas pre-impresas con códigos únicos.
    Guarda registros en BD antes de generar PDFs.
    """
    db = SessionLocal()
    
    try:
        # Obtener postulantes
        if postulantes_ids:
            postulantes = db.query(Postulante).filter(Postulante.id.in_(postulantes_ids)).all()
        elif cantidad:
            postulantes = db.query(Postulante).limit(cantidad).all()
        else:
            raise HTTPException(status_code=400, detail="Especifica 'cantidad' o 'postulantes_ids'")
        
        if not postulantes:
            raise HTTPException(status_code=404, detail="No hay postulantes")
        
        # Crear carpeta
        crear_directorio_generadas()
        
        hojas_generadas = []
        
        for postulante in postulantes:
            print(f"\n📄 Procesando: {postulante.dni}")
            
            # Verificar si ya existe
            hoja_existente = db.query(HojaRespuesta).filter_by(
                postulante_id=postulante.id,
                proceso_admision=proceso_admision,
                estado="generada"
            ).first()
            
            if hoja_existente:
                # Reimpresión: actualizar código
                print(f"   🔄 REIMPRESIÓN")
                codigo_hoja = generar_codigo_hoja_unico()
                
                while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                    codigo_hoja = generar_codigo_hoja_unico()
                
                hoja_existente.codigo_hoja = codigo_hoja
                hoja_existente.updated_at = datetime.now(timezone.utc)
                hoja = hoja_existente
                
            else:
                # Primera vez
                print(f"   ✨ PRIMERA VEZ")
                codigo_hoja = generar_codigo_hoja_unico()
                
                while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                    codigo_hoja = generar_codigo_hoja_unico()
                
                hoja = HojaRespuesta(
                    postulante_id=postulante.id,
                    dni_profesor=dni_profesor,
                    codigo_aula=codigo_aula,
                    codigo_hoja=codigo_hoja,
                    proceso_admision=proceso_admision,
                    estado="generada"
                )
                db.add(hoja)
            
            print(f"   📋 Código: {codigo_hoja}")
            
            # Generar PDF
            pdf_path = f"hojas_generadas/{codigo_hoja}.pdf"
            
            resultado_pdf = generar_hoja_respuestas_pdf(
                output_path=pdf_path,
                dni_postulante=postulante.dni,
                codigo_aula=codigo_aula,
                dni_profesor=dni_profesor,
                codigo_hoja=codigo_hoja,
                proceso=proceso_admision
            )
            
            hoja.imagen_url = pdf_path
            
            print(f"   ✅ PDF: {pdf_path}")
            
            hojas_generadas.append({
                "postulante": f"{postulante.nombres} {postulante.apellido_paterno}",
                "dni": postulante.dni,
                "codigo_hoja": codigo_hoja,
                "pdf": pdf_path,
                "reimpresion": hoja_existente is not None
            })
        
        # COMMIT
        db.commit()
        print(f"\n✅ COMMIT - {len(hojas_generadas)} hojas guardadas")
        
        return {
            "success": True,
            "total_generadas": len(hojas_generadas),
            "hojas": hojas_generadas
        }
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================================================
# ENDPOINT: GENERAR HOJAS (LEGACY - para compatibilidad con frontend actual)
# ============================================================================

# ============================================================================
# ENDPOINT CORREGIDO - Con profesor y aula seleccionables
# ============================================================================

@app.post("/api/generar-hojas")
async def generar_hojas(
    tipo: str = Form(...),
    postulante_id: Optional[int] = Form(None),
    rango_inicio: Optional[int] = Form(None),
    rango_fin: Optional[int] = Form(None),
    cantidad_hojas: Optional[int] = Form(100),
    incluir_datos: bool = Form(True),
    incluir_firma: bool = Form(True),
    proceso_admision: str = Form("2025-2"),
    # CAMBIO: Ahora son opcionales, se obtienen de BD si no se envían
    codigo_aula: Optional[str] = Form(None),
    dni_profesor: Optional[str] = Form(None)
):
    """
    Genera hojas de respuestas y las registra en BD.
    
    CORREGIDO:
    - Si no se envía código_aula, usa el primero disponible en BD
    - Si no se envía dni_profesor, usa el primero disponible en BD
    - Logs detallados para debugging
    """
    db = SessionLocal()
    
    try:
        # ====================================================================
        # 1. OBTENER AULA Y PROFESOR (si no vienen del frontend)
        # ====================================================================
        
        if not codigo_aula:
            primera_aula = db.query(Aula).first()
            if primera_aula:
                codigo_aula = primera_aula.codigo
                print(f"📍 Usando aula por defecto: {codigo_aula}")
            else:
                raise HTTPException(status_code=400, detail="No hay aulas registradas en BD")
        
        if not dni_profesor:
            primer_profesor = db.query(Profesor).first()
            if primer_profesor:
                dni_profesor = primer_profesor.dni
                print(f"👨‍🏫 Usando profesor por defecto: {dni_profesor} ({primer_profesor.nombres})")
            else:
                raise HTTPException(status_code=400, detail="No hay profesores registrados en BD")
        
        # Verificar que existan en BD
        aula = db.query(Aula).filter_by(codigo=codigo_aula).first()
        if not aula:
            raise HTTPException(status_code=404, detail=f"Aula {codigo_aula} no existe")
        
        profesor = db.query(Profesor).filter_by(dni=dni_profesor).first()
        if not profesor:
            raise HTTPException(status_code=404, detail=f"Profesor {dni_profesor} no existe")
        
        print(f"✅ Aula validada: {codigo_aula} - {aula.nombre}")
        print(f"✅ Profesor validado: {dni_profesor} - {profesor.nombres}")
        
        # ====================================================================
        # 2. OBTENER POSTULANTES
        # ====================================================================
        
        postulantes_data = []
        
        if tipo == "todos":
            postulantes = db.query(Postulante).all()
            print(f"📋 Obtenidos {len(postulantes)} postulantes (todos)")
            
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,
                    "postulante_id": p.id,
                    "datos": {
                        "dni": p.dni,
                        "nombres": p.nombres,
                        "apellido_paterno": p.apellido_paterno,
                        "apellido_materno": p.apellido_materno,
                        "programa": p.programa_educativo
                    } if incluir_datos else None
                })
                
        elif tipo == "individual":
            postulante = db.query(Postulante).filter_by(id=postulante_id).first()
            if not postulante:
                raise HTTPException(status_code=404, detail="Postulante no encontrado")
            
            print(f"📋 Postulante individual: {postulante.dni}")
            
            postulantes_data.append({
                "codigo": postulante.dni,
                "postulante_id": postulante.id,
                "datos": {
                    "dni": postulante.dni,
                    "nombres": postulante.nombres,
                    "apellido_paterno": postulante.apellido_paterno,
                    "apellido_materno": postulante.apellido_materno,
                    "programa": postulante.programa_educativo
                } if incluir_datos else None
            })
            
        elif tipo == "rango":
            postulantes = db.query(Postulante).slice(rango_inicio - 1, rango_fin).all()
            print(f"📋 Obtenidos {len(postulantes)} postulantes (rango {rango_inicio}-{rango_fin})")
            
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,
                    "postulante_id": p.id,
                    "datos": {
                        "dni": p.dni,
                        "nombres": p.nombres,
                        "apellido_paterno": p.apellido_paterno,
                        "apellido_materno": p.apellido_materno,
                        "programa": p.programa_educativo
                    } if incluir_datos else None
                })
                
        elif tipo == "sin_identificar":
            print(f"📋 Generando {cantidad_hojas} hojas sin identificar")
            for i in range(cantidad_hojas):
                postulantes_data.append({
                    "codigo": f"SIN-ID-{i+1:04d}",
                    "postulante_id": None,
                    "datos": None
                })
        
        if not postulantes_data:
            raise HTTPException(status_code=400, detail="No hay postulantes para generar hojas")
        
        # ====================================================================
        # 3. GENERAR PDFs Y REGISTRAR EN BD
        # ====================================================================
        
        temp_dir = tempfile.mkdtemp()
        pdf_files = []
        hojas_registradas = []
        hojas_sin_registrar = []
        
        crear_directorio_generadas()
        
        for idx, item in enumerate(postulantes_data, 1):
            print(f"\n{'='*60}")
            print(f"📄 Procesando hoja {idx}/{len(postulantes_data)}")
            print(f"   DNI: {item['codigo']}")
            print(f"   Postulante ID: {item['postulante_id']}")
            
            # Generar código único
            codigo_hoja = generar_codigo_hoja_unico()
            
            # Verificar que sea único
            intentos = 0
            while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                codigo_hoja = generar_codigo_hoja_unico()
                intentos += 1
                if intentos > 10:
                    raise Exception("No se pudo generar código único después de 10 intentos")
            
            print(f"   Código generado: {codigo_hoja}")
            
            # REGISTRAR EN BD
            if item['postulante_id']:
                try:
                    hoja = HojaRespuesta(
                        postulante_id=item['postulante_id'],
                        dni_profesor=dni_profesor,
                        codigo_aula=codigo_aula,
                        codigo_hoja=codigo_hoja,
                        proceso_admision=proceso_admision,
                        estado="generada"
                    )
                    db.add(hoja)
                    db.flush()  # Para obtener el ID
                    
                    hojas_registradas.append({
                        "codigo_hoja": codigo_hoja,
                        "dni": item['codigo'],
                        "hoja_id": hoja.id
                    })
                    print(f"   ✅ Registrado en BD (ID: {hoja.id})")
                    
                except Exception as e:
                    print(f"   ⚠️ Error al registrar en BD: {str(e)}")
                    hojas_sin_registrar.append({
                        "codigo_hoja": codigo_hoja,
                        "dni": item['codigo'],
                        "error": str(e)
                    })
            else:
                print(f"   ⏭️ Sin postulante_id, no se registra en BD")
                hojas_sin_registrar.append({
                    "codigo_hoja": codigo_hoja,
                    "dni": item['codigo'],
                    "razon": "sin_identificar"
                })
            
            # GENERAR PDF
            filename = f"hoja_{item['codigo']}_{codigo_hoja}.pdf"
            filepath = os.path.join(temp_dir, filename)
            
            try:
                generar_hoja_respuestas_pdf(
                    output_path=filepath,
                    dni_postulante=item['codigo'],
                    codigo_aula=codigo_aula,
                    dni_profesor=dni_profesor,
                    codigo_hoja=codigo_hoja,
                    proceso=proceso_admision
                )
                pdf_files.append(filepath)
                print(f"   ✅ PDF generado: {filename}")
                
            except Exception as e:
                print(f"   ❌ Error al generar PDF: {str(e)}")
                raise
        
        # ====================================================================
        # 4. COMMIT A BD
        # ====================================================================
        
        try:
            db.commit()
            print(f"\n{'='*60}")
            print(f"✅ COMMIT EXITOSO")
            print(f"   Hojas registradas en BD: {len(hojas_registradas)}")
            print(f"   Hojas sin registrar: {len(hojas_sin_registrar)}")
            
        except Exception as e:
            db.rollback()
            print(f"\n❌ ERROR EN COMMIT: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al guardar en BD: {str(e)}")
        
        # ====================================================================
        # 5. CREAR ZIP
        # ====================================================================
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for pdf_file in pdf_files:
                zip_file.write(pdf_file, os.path.basename(pdf_file))
        
        zip_buffer.seek(0)
        
        # Limpiar temporales
        for pdf_file in pdf_files:
            os.remove(pdf_file)
        os.rmdir(temp_dir)
        
        # ====================================================================
        # 6. RESPUESTA
        # ====================================================================
        
        filename = f"hojas_respuestas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        print(f"\n✅ Proceso completado")
        print(f"   Archivo ZIP: {filename}")
        print(f"   Total PDFs: {len(pdf_files)}")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Total-Hojas": str(len(pdf_files)),
                "X-Hojas-Registradas": str(len(hojas_registradas)),
                "X-Hojas-Sin-Registrar": str(len(hojas_sin_registrar))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



# ============================================================================
# ENDPOINT: PROCESAR HOJA COMPLETA
# ============================================================================

"""
ENDPOINT COMPLETO Y SANEADO - /api/procesar-hoja-completa
Reemplazar en main.py desde la línea del @app.post hasta el final del endpoint
"""

@app.post("/api/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    metadata_captura: str = Form(None),
    image_hash: str = Form(None),
    request: Request = None
):
    """
    Procesa hoja capturada con Vision AI V2:
    1. Pre-procesa con OpenCV
    2. Extrae códigos + respuestas (fallback 4 APIs)
    3. Valida códigos en BD
    4. Guarda imagen + respuestas
    5. Califica si existe gabarito
    """
    db = SessionLocal()
    inicio = time.time()
    
    try:
        # ====================================================================
        # 1. PREPARAR IMAGEN
        # ====================================================================
        crear_directorio_capturas()
        temp_filepath, temp_filename = guardar_foto_temporal(file)
        
        # Parsear metadata de captura
        metadata_dict = {}
        if metadata_captura:
            try:
                metadata_dict = json.loads(metadata_captura)
            except:
                pass
        
        if request:
            metadata_dict['ip_address'] = request.client.host
        metadata_dict['image_hash'] = image_hash
        
        # ====================================================================
        # 2. PROCESAR CON VISION AI V2 (OpenCV + APIs)
        # ====================================================================
        print("📸 Procesando con Vision AI V2...")
        resultado_vision = await procesar_con_api_seleccionada(temp_filepath)
        
        if not resultado_vision["success"]:
            raise HTTPException(
                status_code=500,
                detail=resultado_vision.get("error", "Error en Vision AI")
            )
        
        # ====================================================================
        # 3. EXTRAER DATOS
        # ====================================================================
        datos = resultado_vision["datos"]
        codigo_hoja = datos.get("codigo_hoja")
        dni_postulante = datos.get("dni_postulante")
        dni_profesor = datos.get("dni_profesor")
        codigo_aula = datos.get("codigo_aula")
        proceso = datos.get("proceso_admision", "2025-2")
        respuestas_alumno = datos.get("respuestas", [])
        
        # Metadata de procesamiento
        api_utilizada = resultado_vision.get("api", "unknown")
        modelo_usado = resultado_vision.get("modelo", "unknown")
        tiempo_procesamiento = resultado_vision.get("tiempo_procesamiento", 0.0)
        preprocessing_usado = resultado_vision.get("preprocessing", {}).get("used", False)
        
        # Estadísticas
        stats = datos.get("stats", {})
        respuestas_validas = stats.get("validas", len([r for r in respuestas_alumno if r]))
        respuestas_vacias = stats.get("vacias", len([r for r in respuestas_alumno if not r]))
        requieren_revision = stats.get("requieren_revision", 0)
        
        # Log
        print(f"✅ API: {api_utilizada.upper()} | Modelo: {modelo_usado}")
        print(f"⏱️  Tiempo: {tiempo_procesamiento:.2f}s")
        print(f"📊 Válidas: {respuestas_validas}/100 | Vacías: {respuestas_vacias}")
        if preprocessing_usado:
            print(f"🔧 OpenCV: activado")
        
        # ====================================================================
        # 4. BUSCAR HOJA EN BD
        # ====================================================================
        hoja = db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first()
        
        if not hoja:
            raise HTTPException(
                status_code=404,
                detail=f"No existe hoja con código {codigo_hoja}"
            )
        
        # ====================================================================
        # 5. VALIDAR CÓDIGOS
        # ====================================================================
        estado_val, mensajes, datos_validados = validar_codigos(
            dni_postulante, dni_profesor, codigo_aula, db
        )
        
        postulante = datos_validados.get("postulante")
        
        if not postulante:
            raise HTTPException(
                status_code=404,
                detail=f"Postulante con DNI {dni_postulante} no encontrado"
            )
        
        # ====================================================================
        # 6. GUARDAR IMAGEN CON NOMBRE FINAL
        # ====================================================================
        filename_final = f"{codigo_hoja}-{dni_postulante}-{codigo_aula}-{dni_profesor}.jpeg"
        filepath_final = f"app/hojas_capturadas/{filename_final}"
        shutil.copy(temp_filepath, filepath_final)
        
        # ====================================================================
        # 7. VERIFICAR GABARITO Y CALIFICAR
        # ====================================================================
        tiene_gabarito = gabarito_existe(db, proceso)
        calificacion_data = None
        
        if tiene_gabarito:
            calificacion = calcular_calificacion(
                respuestas_alumno,
                gabarito_existe(db, proceso),  # Obtener gabarito
                db
            )
            
            nota_final = calificacion["nota"]
            correctas_count = calificacion["correctas"]
            estado_hoja = "completado"
            mensajes.append("✅ Calificada automáticamente")
            
            calificacion_data = {
                "nota": nota_final,
                "correctas": correctas_count,
                "incorrectas": calificacion["incorrectas"],
                "en_blanco": calificacion["en_blanco"]
            }
        else:
            nota_final = None
            correctas_count = None
            estado_hoja = "pendiente_calificar"
            mensajes.append("⏳ Pendiente de calificación")
        
        # ====================================================================
        # 8. ACTUALIZAR HOJA EN BD
        # ====================================================================
        hoja.imagen_url = filepath_final
        hoja.api_utilizada = api_utilizada
        hoja.estado = estado_hoja
        hoja.respuestas_detectadas = len(respuestas_alumno)
        hoja.tiempo_procesamiento = tiempo_procesamiento
        hoja.nota_final = nota_final
        hoja.respuestas_correctas_count = correctas_count
        hoja.fecha_calificacion = datetime.now(timezone.utc) if tiene_gabarito else None
        hoja.observaciones = ", ".join(mensajes)
        
        # Metadata completa
        hoja.metadata_json = json.dumps({
            "captura": metadata_dict,
            "api": api_utilizada,
            "modelo": modelo_usado,
            "preprocessing": preprocessing_usado,
            "stats": {
                "validas": respuestas_validas,
                "vacias": respuestas_vacias,
                "requieren_revision": requieren_revision
            },
            "validacion": mensajes
        }, ensure_ascii=False)
        
        # ====================================================================
        # 9. GUARDAR RESPUESTAS INDIVIDUALES
        # ====================================================================
        for i, resp_raw in enumerate(respuestas_alumno, 1):
            respuesta = Respuesta(
                hoja_respuesta_id=hoja.id,
                numero_pregunta=i,
                respuesta_marcada=resp_raw,
                confianza=1.0 if resp_raw else 0.8,
                marcada_revision=False
            )
            db.add(respuesta)
        
        db.commit()
        db.refresh(hoja)
        
        # ====================================================================
        # 10. RETORNAR RESPUESTA
        # ====================================================================
        return {
            "success": True,
            "codigo_hoja": codigo_hoja,
            "postulante": {
                "dni": postulante.dni,
                "nombres": f"{postulante.nombres} {postulante.apellido_paterno}",
                "programa": postulante.programa_educativo
            },
            "procesamiento": {
                "api": api_utilizada,
                "modelo": modelo_usado,
                "tiempo": f"{tiempo_procesamiento:.2f}s",
                "opencv_usado": preprocessing_usado
            },
            "respuestas_detectadas": len(respuestas_alumno),
            "stats": {
                "validas": respuestas_validas,
                "vacias": respuestas_vacias,
                "requieren_revision": requieren_revision
            },
            "validacion": {
                "mensajes": mensajes,
                "estado": "ok" if estado_val else "con_observaciones"
            },
            "calificacion": calificacion_data
        }
        
    except HTTPException as he:
        db.rollback()
        raise he
        
    except DataError as de:
        db.rollback()
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "titulo": "Error de Datos",
                    "mensaje": "Algunos datos exceden el límite permitido.",
                    "icono": "⚠️",
                    "tipo": "database_error"
                }
            }
        )
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "titulo": "Error Inesperado",
                    "mensaje": str(e),
                    "icono": "❌",
                    "tipo": "unknown_error"
                }
            }
        )
        
    finally:
        db.close()


# ============================================================================
# ENDPOINT: REGISTRAR GABARITO
# ============================================================================

@app.post("/api/registrar-gabarito-manual")
async def registrar_gabarito_manual(
    respuestas: str = Form(...),
    proceso_admision: str = Form("2025-2")
):
    """Registra las respuestas correctas manualmente"""
    db = SessionLocal()
    
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
    finally:
        db.close()


# ============================================================================
# ENDPOINT: CALIFICAR HOJAS PENDIENTES
# ============================================================================

@app.post("/api/calificar-hojas-pendientes")
async def calificar_hojas_pendientes(proceso_admision: str = "2025-2"):
    """Califica todas las hojas pendientes después de registrar gabarito"""
    db = SessionLocal()
    
    try:
        # Verificar gabarito
        if not gabarito_existe(proceso_admision, db):
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
                calificacion = calcular_calificacion(
                    respuestas_array,
                    proceso_admision,
                    db
                )
                
                # Actualizar
                hoja.nota_final = calificacion["nota"]
                hoja.respuestas_correctas_count = calificacion["correctas"]
                hoja.estado = "completado"
                hoja.fecha_calificacion = datetime.now(timezone.utc)
                
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
    finally:
        db.close()


# ============================================================================
# ENDPOINT: VERIFICAR CÓDIGOS
# ============================================================================

@app.get("/api/verificar-codigos")
async def verificar_codigos():
    """Verifica códigos guardados en BD"""
    db = SessionLocal()
    try:
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
    finally:
        db.close()


# ============================================================================
# ENDPOINT: RESULTADOS
# ============================================================================

@app.get("/api/resultados/{proceso_admision}")
async def obtener_resultados(proceso_admision: str):
    """Obtiene ranking de postulantes"""
    db = SessionLocal()
    
    try:
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
        
    finally:
        db.close()


# ============================================================================
# AGREGAR ESTOS ENDPOINTS AL MAIN.PY
# Para que el frontend pueda obtener listas de profesores y aulas
# ============================================================================

@app.get("/api/profesores")
async def obtener_profesores():
    """Obtiene lista de profesores para selección"""
    db = SessionLocal()
    try:
        profesores = db.query(Profesor).all()
        
        return {
            "success": True,
            "total": len(profesores),
            "profesores": [
                {
                    "id": p.id,
                    "dni": p.dni,
                    "nombres": p.nombres,
                    "apellido_paterno": p.apellido_paterno,
                    "apellido_materno": p.apellido_materno,
                    "nombre_completo": f"{p.apellido_paterno} {p.apellido_materno}, {p.nombres}"
                }
                for p in profesores
            ]
        }
    finally:
        db.close()


@app.get("/api/aulas")
async def obtener_aulas():
    """Obtiene lista de aulas para selección"""
    db = SessionLocal()
    try:
        aulas = db.query(Aula).all()
        
        return {
            "success": True,
            "total": len(aulas),
            "aulas": [
                {
                    "id": a.id,
                    "codigo": a.codigo,
                    "nombre": a.nombre,
                    "capacidad": a.capacidad
                }
                for a in aulas
            ]
        }
    finally:
        db.close()


@app.post("/api/verificar-datos-generacion")
async def verificar_datos_generacion():
    """
    Verifica que existan datos necesarios para generar hojas.
    Útil para mostrar warnings en frontend.
    """
    db = SessionLocal()
    try:
        total_postulantes = db.query(Postulante).count()
        total_profesores = db.query(Profesor).count()
        total_aulas = db.query(Aula).count()
        
        errores = []
        warnings = []
        
        if total_postulantes == 0:
            errores.append("No hay postulantes registrados")
        
        if total_profesores == 0:
            errores.append("No hay profesores registrados")
        
        if total_aulas == 0:
            errores.append("No hay aulas registradas")
        
        if total_postulantes < 10:
            warnings.append(f"Solo hay {total_postulantes} postulante(s) registrado(s)")
        
        puede_generar = len(errores) == 0
        
        return {
            "success": True,
            "puede_generar": puede_generar,
            "errores": errores,
            "warnings": warnings,
            "estadisticas": {
                "postulantes": total_postulantes,
                "profesores": total_profesores,
                "aulas": total_aulas
            }
        }
    finally:
        db.close()


# ============================================================================
# AGREGAR EN main.py - Manejo de errores amigable
# ============================================================================

# Diccionario de errores traducidos
ERRORES_AMIGABLES = {
    "404": {
        "titulo": "Hoja No Encontrada",
        "mensaje": "El código de hoja no existe en el sistema. Verifica que la hoja esté registrada.",
        "icono": "🔍",
        "color": "#ef4444"
    },
    "StringDataRightTruncation": {
        "titulo": "Error de Datos",
        "mensaje": "Algunos datos son demasiado largos para guardar. Contacta al administrador.",
        "icono": "⚠️",
        "color": "#f59e0b"
    },
    "no_gabarito": {
        "titulo": "Sin Gabarito",
        "mensaje": "Hoja procesada correctamente. Será calificada cuando se registre el gabarito.",
        "icono": "⏳",
        "color": "#3b82f6"
    },
    "gps_required": {
        "titulo": "GPS Requerido",
        "mensaje": "Debes activar la ubicación para capturar hojas. Es un requisito de seguridad.",
        "icono": "📍",
        "color": "#ef4444"
    },
    "all_apis_failed": {
        "titulo": "Error de Procesamiento",
        "mensaje": "No se pudo procesar la imagen. Intenta con mejor iluminación o ángulo.",
        "icono": "❌",
        "color": "#ef4444"
    }
}

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)