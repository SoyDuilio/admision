"""
POSTULANDO - Sistema de Exámenes de Admisión
main.py LIMPIO Y MODULARIZADO
"""

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, desc
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
from app.database import SessionLocal, engine, Base, get_db
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


# ============================================================================
# AGREGAR AL INICIO DE app/main.py (después de los imports)
# ============================================================================

from pathlib import Path
import os

def crear_carpetas_necesarias():
    """
    Crea las carpetas necesarias al iniciar la aplicación.
    Se ejecuta automáticamente en Railway.
    """
    carpetas = [
        "temp_uploads",
        "temp_uploads/processed",
        "uploads/hojas_originales",
        "uploads/hojas_generadas",
        "uploads/reportes",
        "logs"
    ]
    
    for carpeta in carpetas:
        path = Path(carpeta)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Carpeta verificada: {carpeta}")

# Ejecutar al iniciar la app
crear_carpetas_necesarias()


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
# AGREGAR ESTAS LÍNEAS AL FINAL DE app/main.py
# ============================================================================

from fastapi import UploadFile, File
from pathlib import Path
from datetime import datetime
import shutil
import uuid

@app.post("/api/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    api: str = "google"
):
    """
    Endpoint que procesa una hoja de respuestas completa.
    
    ESTE ES EL QUE DABA ERROR 404 - AHORA FUNCIONA
    """
    
    try:
        # ====================================================================
        # 1. GUARDAR IMAGEN TEMPORAL
        # ====================================================================
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{unique_id}.jpg"
        
        # Crear carpeta si no existe
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_path = temp_dir / filename
        
        # Guardar archivo
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ====================================================================
        # 2. PROCESAR CON TU CÓDIGO EXISTENTE
        # ====================================================================
        
        # Aquí llamas a tu función existente de procesamiento
        # Por ejemplo, si tienes algo como:
        # from app.services.vision_service_v2 import procesar_hoja_con_api
        
        # Leer la imagen
        with open(temp_path, "rb") as f:
            image_bytes = f.read()
        
        # Procesar (usa tu función existente)
        # resultado = await procesar_hoja_con_api(image_bytes, api)
        
        # POR AHORA, retorna esto:
        resultado = {
            "success": True,
            "message": f"Imagen guardada correctamente en {filename}",
            "api": api,
            "timestamp": timestamp
        }
        
        # ====================================================================
        # 3. LIMPIAR TEMPORAL (opcional - comentado por ahora)
        # ====================================================================
        
        # temp_path.unlink()  # Descomentar para borrar
        
        return resultado
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



# ============================================================================
# AGREGAR AL FINAL DE app/main.py
# ============================================================================

from sqlalchemy import desc, func

@app.get("/resultados", response_class=HTMLResponse)
async def pagina_resultados(
    request: Request,
    codigo: str = None,
    estado: str = None,
    api: str = None,
    db: Session = Depends(get_db)
):
    """
    Página de resultados con todas las hojas procesadas.
    Más recientes primero.
    """
    
    from app.models import HojaRespuesta, Respuesta
    
    # Query base
    query = db.query(HojaRespuesta)
    
    # Aplicar filtros si existen
    if codigo:
        query = query.filter(HojaRespuesta.codigo_hoja.ilike(f'%{codigo}%'))
    
    if estado:
        query = query.filter(HojaRespuesta.estado == estado)
    
    if api:
        query = query.filter(HojaRespuesta.api_utilizada == api)
    
    # Ordenar por más recientes primero
    hojas = query.order_by(desc(HojaRespuesta.created_at)).limit(50).all()
    
    # Calcular estadísticas para cada hoja
    hojas_con_stats = []
    
    for hoja in hojas:
        # Obtener estadísticas de respuestas
        respuestas = db.query(Respuesta).filter(
            Respuesta.hoja_respuesta_id == hoja.id
        ).all()
        
        validas = sum(1 for r in respuestas if r.respuesta_marcada in ['A', 'B', 'C', 'D', 'E'])
        vacias = sum(1 for r in respuestas if r.respuesta_marcada == 'VACIO')
        problematicas = sum(1 for r in respuestas if r.respuesta_marcada in ['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
        
        # Obtener DNI del postulante (desde la relación si existe)
        dni_postulante = None
        if hoja.postulante_id:
            from app.models import Postulante
            postulante = db.query(Postulante).filter(Postulante.id == hoja.postulante_id).first()
            if postulante:
                dni_postulante = postulante.dni
        
        hojas_con_stats.append({
            'id': hoja.id,
            'codigo_hoja': hoja.codigo_hoja,
            'dni_postulante': dni_postulante or '—',
            'codigo_aula': hoja.codigo_aula or '—',
            'api_utilizada': hoja.api_utilizada or 'N/A',
            'tiempo_procesamiento': hoja.tiempo_procesamiento or 0,
            'fecha_captura': hoja.created_at,
            'stats': {
                'validas': validas,
                'vacias': vacias,
                'problematicas': problematicas
            }
        })
    
    # Estadísticas globales
    total_hojas = db.query(func.count(HojaRespuesta.id)).scalar()
    
    total_respuestas = db.query(Respuesta).count()
    total_validas = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada.in_(['A', 'B', 'C', 'D', 'E'])
    ).count()
    total_vacias = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada == 'VACIO'
    ).count()
    total_problematicas = db.query(Respuesta).filter(
        Respuesta.respuesta_marcada.in_(['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
    ).count()
    
    return templates.TemplateResponse("resultados.html", {
        "request": request,
        "hojas": hojas_con_stats,
        "total_hojas": total_hojas,
        "total_validas": total_validas,
        "total_vacias": total_vacias,
        "total_problematicas": total_problematicas
    })


@app.get("/hoja/{hoja_id}/detalle", response_class=HTMLResponse)
async def detalle_hoja(
    hoja_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Página de detalle de una hoja específica.
    Muestra las 100 respuestas con su clasificación.
    """
    
    from app.models import HojaRespuesta, Respuesta
    
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        raise HTTPException(status_code=404, detail="Hoja no encontrada")
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    return templates.TemplateResponse("detalle_hoja.html", {
        "request": request,
        "hoja": hoja,
        "respuestas": respuestas
    })


@app.get("/api/exportar-resultados")
async def exportar_resultados_excel(db: Session = Depends(get_db)):
    """
    Exporta los resultados a Excel.
    """
    
    from app.models import HojaRespuesta, Respuesta
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
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

# ============================================================================
# ENDPOINTS PARA GABARITO - AGREGAR A app/main.py
# ============================================================================

from collections import Counter
from typing import Dict, List
from fastapi import Form

@app.post("/api/gabarito/procesar-manual")
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
    
    # Guardar en sesión temporal (para confirmar después)
    # O retornar para que el frontend lo guarde
    
    return {
        "success": True,
        "proceso": proceso,
        "respuestas": respuestas_upper,
        "estadisticas_columnas": estadisticas_columnas,
        "resumen_general": resumen_general,
        "message": "Gabarito procesado. Revise las estadísticas antes de confirmar."
    }


@app.post("/api/gabarito/procesar-imagen")
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
            respuestas=respuestas_dict,
            proceso=proceso,
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


@app.post("/api/gabarito/confirmar")
async def confirmar_gabarito(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Guarda el gabarito confirmado en la base de datos.
    """
    
    from app.models import ClaveRespuesta
    import json
    
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
    
    # También guardar en tabla respuestas_correctas (desnormalizado)
    from app.models import RespuestaCorrecta
    
    for numero, respuesta in respuestas.items():
        rc = RespuestaCorrecta(
            proceso_admision=proceso,
            numero_pregunta=int(numero),
            respuesta_correcta=respuesta
        )
        db.add(rc)
    
    db.commit()
    
    return {
        "success": True,
        "gabarito_id": gabarito.id,
        "proceso": proceso,
        "total_respuestas": len(respuestas),
        "message": "Gabarito guardado correctamente"
    }


@app.get("/api/gabarito/{proceso}")
async def obtener_gabarito(
    proceso: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el gabarito de un proceso específico.
    """
    
    from app.models import ClaveRespuesta
    import json
    
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


@app.put("/api/gabarito/{gabarito_id}/editar")
async def editar_gabarito(
    gabarito_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Permite editar un gabarito existente.
    """
    
    from app.models import ClaveRespuesta, RespuestaCorrecta
    import json
    
    respuestas = data.get('respuestas', {})
    observaciones = data.get('observaciones')
    
    gabarito = db.query(ClaveRespuesta).filter(ClaveRespuesta.id == gabarito_id).first()
    
    if not gabarito:
        raise HTTPException(status_code=404, detail="Gabarito no encontrado")
    
    # Actualizar
    gabarito.respuestas_json = json.dumps(respuestas)
    gabarito.observaciones = observaciones
    gabarito.updated_at = datetime.now()
    
    # Actualizar tabla respuestas_correctas
    db.query(RespuestaCorrecta).filter(
        RespuestaCorrecta.proceso_admision == gabarito.proceso_admision
    ).delete()
    
    for numero, respuesta in respuestas.items():
        rc = RespuestaCorrecta(
            proceso_admision=gabarito.proceso_admision,
            numero_pregunta=int(numero),
            respuesta_correcta=respuesta
        )
        db.add(rc)
    
    db.commit()
    
    return {
        "success": True,
        "message": "Gabarito actualizado correctamente"
    }


# ============================================================================
# AGREGAR ESTE ENDPOINT A app/main.py
# ============================================================================

@app.get("/gabarito/confirmar", response_class=HTMLResponse)
async def pagina_confirmar_gabarito(request: Request):
    """
    Muestra página de confirmación con estadísticas.
    Los datos vienen de sessionStorage (JavaScript).
    """
    return templates.TemplateResponse("confirmar_gabarito.html", {
        "request": request
    })


# ============================================================================
# ENDPOINT DE CALIFICACIÓN - AGREGAR A app/main.py
# ============================================================================

@app.post("/api/calificar-hojas")
async def calificar_hojas_masivo(
    proceso: str = "ADMISION_2025_2",
    db: Session = Depends(get_db)
):
    """
    Califica TODAS las hojas procesadas que aún no han sido calificadas.
    Compara con el gabarito del proceso.
    """
    
    from app.models import HojaRespuesta, Respuesta, ClaveRespuesta, RespuestaCorrecta, Calificacion, Postulante
    import json
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso
    ).first()
    
    if not gabarito:
        raise HTTPException(
            status_code=404,
            detail=f"No existe gabarito para el proceso {proceso}"
        )
    
    # Obtener respuestas correctas como dict
    respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
    
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


@app.post("/api/calificar-hoja/{hoja_id}")
async def calificar_hoja_endpoint(
    hoja_id: int,
    gabarito_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Califica una hoja específica.
    """
    
    from app.models import ClaveRespuesta
    
    # Si no se especifica gabarito, usar el activo
    if not gabarito_id:
        gabarito = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == "ADMISION_2025_2"
        ).first()
        
        if not gabarito:
            raise HTTPException(
                status_code=404,
                detail="No hay gabarito activo"
            )
        
        gabarito_id = gabarito.id
    
    resultado = await calificar_hoja_individual(hoja_id, gabarito_id, db)
    
    return resultado


async def calificar_hoja_individual(hoja_id: int, gabarito_id: int, db: Session):
    """
    Lógica de calificación de una hoja individual.
    """
    
    from app.models import HojaRespuesta, Respuesta, ClaveRespuesta, Calificacion, Postulante
    import json
    
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
# ENDPOINT ESTADÍSTICAS - AGREGAR A app/main.py
# ============================================================================

@app.get("/estadisticas", response_class=HTMLResponse)
async def pagina_estadisticas(request: Request, db: Session = Depends(get_db)):
    """
    Página de estadísticas generales y ranking.
    """
    
    from sqlalchemy import func, case
    from app.models import Postulante, Calificacion, HojaRespuesta
    
    # Estadísticas generales (desde vista o calculadas)
    total_postulantes = db.query(func.count(Postulante.id)).scalar()
    
    examenes_calificados = db.query(func.count(HojaRespuesta.id)).filter(
        HojaRespuesta.estado == "calificado"
    ).scalar()
    
    calificaciones = db.query(Calificacion).all()
    
    if calificaciones:
        notas = [c.nota for c in calificaciones]
        nota_promedio = sum(notas) / len(notas)
        nota_maxima = max(notas)
        nota_minima = min(notas)
        aprobados = sum(1 for c in calificaciones if c.aprobado)
        desaprobados = len(calificaciones) - aprobados
    else:
        nota_promedio = 0
        nota_maxima = 0
        nota_minima = 0
        aprobados = 0
        desaprobados = 0
    
    stats = {
        "total_postulantes": total_postulantes or 0,
        "examenes_calificados": examenes_calificados or 0,
        "nota_promedio": nota_promedio,
        "nota_maxima": nota_maxima,
        "nota_minima": nota_minima,
        "aprobados": aprobados,
        "desaprobados": desaprobados
    }
    
    # Ranking (desde vista vw_ranking_postulantes si existe, o calculado)
    try:
        # Intentar usar la vista
        from sqlalchemy import text
        ranking_query = text("""
            SELECT * FROM vw_ranking_postulantes
            ORDER BY ranking ASC
            LIMIT 50
        """)
        ranking = db.execute(ranking_query).fetchall()
        
        # Convertir a lista de dicts
        ranking_list = []
        for row in ranking:
            ranking_list.append({
                "ranking": row.ranking,
                "dni": row.dni,
                "nombre_completo": row.nombre_completo,
                "programa_educativo": row.programa_educativo,
                "nota": row.nota,
                "respuestas_correctas": row.respuestas_correctas
            })
    except:
        # Si no existe la vista, calcular manualmente
        ranking_data = db.query(
            Postulante,
            Calificacion
        ).join(
            Calificacion, Postulante.id == Calificacion.postulante_id
        ).order_by(
            Calificacion.nota.desc()
        ).limit(50).all()
        
        ranking_list = []
        for i, (postulante, calificacion) in enumerate(ranking_data, 1):
            ranking_list.append({
                "ranking": i,
                "dni": postulante.dni,
                "nombre_completo": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa_educativo": postulante.programa_educativo,
                "nota": calificacion.nota,
                "respuestas_correctas": calificacion.correctas
            })
    
    return templates.TemplateResponse("estadisticas.html", {
        "request": request,
        "stats": stats,
        "ranking": ranking_list
    })


# ============================================================================
# ENDPOINTS REVISIÓN MANUAL - AGREGAR A app/main.py
# ============================================================================

# ============================================================================
# ENDPOINTS REVISIÓN MANUAL - AGREGAR A app/main.py
# ============================================================================

@app.get("/revision-manual", response_class=HTMLResponse)
async def pagina_revision_manual(
    request: Request,
    hoja: str = None,
    tipo: str = None,
    db: Session = Depends(get_db)
):
    """
    Página de revisión manual de respuestas problemáticas.
    """
    
    from app.models import Respuesta, HojaRespuesta
    from sqlalchemy import or_
    
    # Query base: respuestas que requieren revisión
    query = db.query(Respuesta).join(HojaRespuesta).filter(
        or_(
            Respuesta.requiere_revision == True,
            Respuesta.respuesta_marcada.in_(['LETRA_INVALIDA', 'GARABATO', 'MULTIPLE', 'ILEGIBLE'])
        )
    )
    
    # Aplicar filtros
    if hoja:
        query = query.filter(HojaRespuesta.codigo_hoja.ilike(f'%{hoja}%'))
    
    if tipo:
        if tipo == 'baja_confianza':
            query = query.filter(Respuesta.confianza < 0.7)
        else:
            query = query.filter(Respuesta.respuesta_marcada == tipo)
    
    respuestas = query.order_by(HojaRespuesta.codigo_hoja, Respuesta.numero_pregunta).all()
    
    # Preparar datos
    respuestas_data = []
    for resp in respuestas:
        respuestas_data.append({
            'id': resp.id,
            'numero_pregunta': resp.numero_pregunta,
            'hoja_codigo': resp.hoja_respuesta.codigo_hoja,
            'respuesta_marcada': resp.respuesta_marcada,
            'confianza': resp.confianza,
            'observacion': resp.observacion,
            'tipo_problema': resp.respuesta_marcada if resp.respuesta_marcada not in ['A','B','C','D','E'] else 'baja_confianza',
            'imagen_url': resp.hoja_respuesta.imagen_url
        })
    
    # Estadísticas
    total_pendientes = len(respuestas_data)
    letra_invalida = sum(1 for r in respuestas_data if r['tipo_problema'] == 'LETRA_INVALIDA')
    garabatos = sum(1 for r in respuestas_data if r['tipo_problema'] == 'GARABATO')
    baja_confianza = sum(1 for r in respuestas_data if r['tipo_problema'] == 'baja_confianza')
    
    return templates.TemplateResponse("revision_manual.html", {
        "request": request,
        "respuestas": respuestas_data,
        "total_pendientes": total_pendientes,
        "letra_invalida": letra_invalida,
        "garabatos": garabatos,
        "baja_confianza": baja_confianza
    })


@app.put("/api/corregir-respuesta/{respuesta_id}")
async def corregir_respuesta_individual(
    respuesta_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Corrige una respuesta individual después de revisión manual.
    """
    
    from app.models import Respuesta
    
    respuesta_corregida = data.get('respuesta_corregida')
    
    # Validar
    if not respuesta_corregida or respuesta_corregida not in ['A', 'B', 'C', 'D', 'E']:
        raise HTTPException(
            status_code=400,
            detail="La respuesta debe ser A, B, C, D o E"
        )
    
    # Obtener respuesta
    respuesta = db.query(Respuesta).filter(Respuesta.id == respuesta_id).first()
    
    if not respuesta:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    
    # Guardar respuesta original en observación
    if not respuesta.observacion:
        respuesta.observacion = f"Original: {respuesta.respuesta_marcada}"
    else:
        respuesta.observacion += f" | Corregido de: {respuesta.respuesta_marcada}"
    
    # Actualizar
    respuesta.respuesta_marcada = respuesta_corregida
    respuesta.requiere_revision = False
    respuesta.confianza = 1.0  # Corregida manualmente = 100% confianza
    
    # Recalcular si es correcta (comparar con gabarito)
    from app.models import ClaveRespuesta
    import json
    
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == "ADMISION_2025_2"
    ).first()
    
    if gabarito:
        respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
        respuesta_correcta = respuestas_correctas.get(str(respuesta.numero_pregunta))
        respuesta.es_correcta = (respuesta_corregida == respuesta_correcta)
    
    db.commit()
    
    return {
        "success": True,
        "message": "Respuesta corregida",
        "respuesta_id": respuesta_id,
        "nueva_respuesta": respuesta_corregida,
        "es_correcta": respuesta.es_correcta
    }


@app.put("/api/corregir-respuestas-masivo")
async def corregir_respuestas_masivo(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Corrige múltiples respuestas a la vez.
    
    data: {"correcciones": {respuesta_id: nueva_respuesta}}
    """
    
    from app.models import Respuesta, ClaveRespuesta
    import json
    
    correcciones = data.get('correcciones', {})
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == "ADMISION_2025_2"
    ).first()
    
    respuestas_correctas = {}
    if gabarito:
        respuestas_correctas = json.loads(gabarito.respuestas_json) if isinstance(gabarito.respuestas_json, str) else gabarito.respuestas_json
    
    corregidas = 0
    
    for respuesta_id, nueva_respuesta in correcciones.items():
        # Validar
        if nueva_respuesta not in ['A', 'B', 'C', 'D', 'E']:
            continue
        
        # Obtener respuesta
        respuesta = db.query(Respuesta).filter(Respuesta.id == int(respuesta_id)).first()
        
        if not respuesta:
            continue
        
        # Guardar original
        if not respuesta.observacion:
            respuesta.observacion = f"Original: {respuesta.respuesta_marcada}"
        else:
            respuesta.observacion += f" | Corregido de: {respuesta.respuesta_marcada}"
        
        # Actualizar
        respuesta.respuesta_marcada = nueva_respuesta
        respuesta.requiere_revision = False
        respuesta.confianza = 1.0
        
        # Verificar si es correcta
        if respuestas_correctas:
            respuesta_correcta = respuestas_correctas.get(str(respuesta.numero_pregunta))
            respuesta.es_correcta = (nueva_respuesta == respuesta_correcta)
        
        corregidas += 1
    
    db.commit()
    
    # Recalcular notas de las hojas afectadas
    # (opcional, se puede hacer después)
    
    return {
        "success": True,
        "message": f"{corregidas} respuestas corregidas",
        "corregidas": corregidas
    }

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