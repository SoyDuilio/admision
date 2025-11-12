"""
POSTULANDO - Sistema de Exámenes de Admisión
"""

from fastapi.responses import StreamingResponse
from fastapi import Form, HTTPException
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from typing import Optional
from io import BytesIO
import zipfile
from datetime import datetime
import uuid
import tempfile
from dotenv import load_dotenv
import os

import random
import string

import time
import shutil


from pathlib import Path


# Importar desde app
from app.database import SessionLocal, engine, Base
from app.models import Postulante, HojaRespuesta, ClaveRespuesta, Calificacion, Profesor, Aula, Respuesta

#from app.api.generador import router as generador_router

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

load_dotenv()

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

#app.include_router(generador_router)

# ============================================
# FUNCIONES AUXILIARES
# ============================================

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

# ============================================
# RUTAS DE PÁGINAS
# ============================================

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
        gabarito_existe = db.query(func.count(ClaveRespuesta.id)).scalar() > 0
        
        return templates.TemplateResponse("registrar_gabarito.html", {
            "request": request,
            "gabarito_ya_existe": gabarito_existe
        })
    finally:
        db.close()

@app.get("/resultados")
async def resultados_page(request: Request):
    """Página de resultados"""
    # TODO: Implementar página de resultados
    return {"message": "Página de resultados en construcción"}

@app.get("/prueba-formal")
async def prueba_formal(request: Request):
    """Página de prueba (demo antigua)"""
    return templates.TemplateResponse("demo.html", {
        "request": request
    })

# ============================================
# ENDPOINTS DE API
# ============================================

@app.get("/resultados")
async def resultados_page():
    """Página de resultados (en construcción)"""
    return {
        "message": "Página de resultados en construcción",
        "status": "coming_soon",
        "nota": "Esta funcionalidad estará disponible una vez que se procesen las primeras hojas"
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

# ============================================
# INCLUIR ROUTERS DE API (comentado por ahora)
# ============================================

# Descomentar cuando estés listo para usar los endpoints de procesamiento
# from app.api import demo_router
# app.include_router(demo_router, prefix="/api", tags=["demo"])


# Instalar dependencias primero:
# pip install reportlab qrcode[pil] pillow --break-system-packages

# Luego agregar estas funciones y endpoint AL FINAL (antes de if __name__):

# ============================================================================
# GENERADOR DE CÓDIGOS Y HOJAS
# ============================================================================

def generar_codigo_unico(tipo: str = "postulante", **kwargs):
    """Genera código alfanumérico único"""
    fecha = datetime.now().strftime("%Y%m%d")
    uuid_short = str(uuid.uuid4())[:4].upper()
    
    if tipo == "postulante":
        dni = kwargs.get('dni', '00000000')
        return f"POST-{dni[-4:]}-{fecha}-{uuid_short}"
    elif tipo == "sin_identificar":
        return f"GEN-{fecha}-{uuid_short}"
    else:
        return f"GEN-{fecha}-{uuid_short}"

def generar_hoja_respuesta_simple(
    output_path: str,
    codigo_unico: str,
    datos_postulante: Optional[dict] = None,
    incluir_firma: bool = True
):
    """
    Genera una hoja de respuestas SIMPLE en texto plano
    (Sin ReportLab por ahora - solo archivo de texto)
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("="* 60 + "\n")
        f.write("I. S. T. Pedro A. Del Águila H. - EXAMEN DE ADMISIÓN 2025\n")
        f.write("HOJA DE RESPUESTAS\n")
        f.write("="* 60 + "\n\n")
        
        if datos_postulante:
            f.write(f"DNI: {datos_postulante.get('dni', '')}\n")
            f.write(f"Nombres: {datos_postulante.get('nombres', '')}\n")
            apellidos = f"{datos_postulante.get('apellido_paterno', '')} {datos_postulante.get('apellido_materno', '')}"
            f.write(f"Apellidos: {apellidos}\n")
            f.write(f"Programa: {datos_postulante.get('programa', '')}\n")
        else:
            f.write("DNI: ____________________\n")
            f.write("Nombres: _________________________________\n")
            f.write("Apellidos: __________________________________________________\n")
        
        f.write(f"\nCÓDIGO: {codigo_unico}\n")
        f.write("="* 60 + "\n\n")
        
        f.write("INSTRUCCIONES:\n")
        f.write("• Marque con X o llene el círculo de la alternativa correcta\n")
        f.write("• Solo una respuesta por pregunta\n")
        f.write("• No realice borrones\n\n")
        
        f.write("RESPUESTAS (marque a, b, c, d o e):\n")
        f.write("-"* 60 + "\n\n")
        
        # Generar grid de 100 preguntas
        for i in range(1, 101):
            f.write(f"{i:3d}. (    )   ")
            if i % 5 == 0:
                f.write("\n")
        
        if incluir_firma:
            f.write("\n\n" + "="* 60 + "\n")
            f.write("Firma del Profesor: _______________________\n")
            f.write("Fecha: ___/___/______\n")


def generar_codigo_hoja():
    """Genera código alfanumérico de 9 caracteres: A2iDñ5RsW"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(9))


# ============================================================================
# GENERADOR DE HOJAS DE RESPUESTAS
# ============================================================================

def generar_hoja_respuesta_pdf(
    output_path: str,
    codigo_postulante: str,  # DNI 8 dígitos
    codigo_profesor: str = None,  # DNI 8 dígitos
    codigo_aula: str = None,  # 4 dígitos
    datos_postulante: dict = None,
    proceso_admision: str = "2025-1",
    incluir_firma: bool = True
):
    """
    Genera hoja de respuestas con códigos según diseño
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    margin = 1.5 * cm
    margin_top = height - 1.5 * cm
    margin_bottom = 1.5 * cm
    
    # Generar código único de hoja
    codigo_hoja = generar_codigo_hoja()
    
    # MARCAS DE ALINEACIÓN
    marca_size = 1 * cm
    marca_grosor = 2.5
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(marca_grosor)
    
    # 4 esquinas
    c.line(margin, margin_top, margin + marca_size, margin_top)
    c.line(margin, margin_top, margin, margin_top - marca_size)
    c.line(width - margin, margin_top, width - margin - marca_size, margin_top)
    c.line(width - margin, margin_top, width - margin, margin_top - marca_size)
    c.line(margin, margin_bottom, margin + marca_size, margin_bottom)
    c.line(margin, margin_bottom, margin, margin_bottom + marca_size)
    c.line(width - margin, margin_bottom, width - margin - marca_size, margin_bottom)
    c.line(width - margin, margin_bottom, width - margin, margin_bottom + marca_size)
    
    # ENCABEZADO
    y = margin_top - 0.8 * cm
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "I. S. T. Pedro A. Del Águila H.")
    y -= 0.6 * cm
    
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, f"EXAMEN DE ADMISIÓN - PROCESO {proceso_admision}")
    y -= 0.4 * cm
    
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "HOJA DE RESPUESTAS")
    y -= 0.7 * cm
    
    c.setStrokeColor(colors.HexColor("#1e3a8a"))
    c.setLineWidth(2)
    c.line(margin, y, width - margin, y)
    y -= 0.7 * cm
    
    # ============================================
    # CÓDIGOS EN CUADROS (según imagen)
    # ============================================
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    
    # Altura de la fila de códigos
    box_height = 1.2 * cm
    y_boxes = y
    
    # Ancho total disponible
    ancho_total = width - 2 * margin
    
    # 3 secciones: DNI Alumno (8 dígitos) | Código Aula (4) | DNI Profesor (8)
    ancho_dni = ancho_total * 0.40  # 40% para DNI alumno
    ancho_aula = ancho_total * 0.20  # 20% para código aula
    ancho_prof = ancho_total * 0.40  # 40% para DNI profesor
    
    # Labels superiores
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(margin + ancho_dni/2, y_boxes + 0.3*cm, "DNI - Alumno (8 dígitos)")
    c.drawCentredString(margin + ancho_dni + ancho_aula/2, y_boxes + 0.3*cm, "Código aula")
    c.drawCentredString(margin + ancho_dni + ancho_aula, y_boxes + 0.3*cm, "4 dígitos")
    c.drawCentredString(margin + ancho_dni + ancho_aula + ancho_prof/2, y_boxes + 0.3*cm, "DNI - Profesor (8 dígitos)")
    
    y_boxes -= 0.5 * cm
    
    # Dibujar cuadros para DNI Alumno (8 cuadros)
    ancho_cuadro_dni = ancho_dni / 8
    for i in range(8):
        x = margin + (i * ancho_cuadro_dni)
        c.rect(x, y_boxes - box_height, ancho_cuadro_dni, box_height)
        if codigo_postulante and i < len(codigo_postulante):
            c.setFont("Courier-Bold", 14)
            c.drawCentredString(x + ancho_cuadro_dni/2, y_boxes - box_height/2 - 0.2*cm, codigo_postulante[i])
    
    # Dibujar cuadros para Código Aula (4 cuadros)
    ancho_cuadro_aula = ancho_aula / 4
    for i in range(4):
        x = margin + ancho_dni + (i * ancho_cuadro_aula)
        c.rect(x, y_boxes - box_height, ancho_cuadro_aula, box_height)
        if codigo_aula and i < len(codigo_aula):
            c.setFont("Courier-Bold", 14)
            c.drawCentredString(x + ancho_cuadro_aula/2, y_boxes - box_height/2 - 0.2*cm, codigo_aula[i])
    
    # Dibujar cuadros para DNI Profesor (8 cuadros)
    ancho_cuadro_prof = ancho_prof / 8
    for i in range(8):
        x = margin + ancho_dni + ancho_aula + (i * ancho_cuadro_prof)
        c.rect(x, y_boxes - box_height, ancho_cuadro_prof, box_height)
        if codigo_profesor and i < len(codigo_profesor):
            c.setFont("Courier-Bold", 14)
            c.drawCentredString(x + ancho_cuadro_prof/2, y_boxes - box_height/2 - 0.2*cm, codigo_profesor[i])
    
    y = y_boxes - box_height - 0.5 * cm
    
    # ============================================
    # CÓDIGO DE HOJA (único, alfanumérico)
    # ============================================
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "Hoja:")
    c.setFont("Courier-Bold", 12)
    c.drawString(margin + 1.5*cm, y, codigo_hoja)
    y -= 0.6 * cm
    
    # Datos postulante
    if datos_postulante:
        c.setFont("Helvetica", 8)
        nombre = f"{datos_postulante.get('apellido_paterno', '')} {datos_postulante.get('apellido_materno', '')}, {datos_postulante.get('nombres', '')}"
        c.drawString(margin, y, nombre.upper()[:60])
        y -= 0.4 * cm
        c.drawString(margin, y, f"Programa: {datos_postulante.get('programa', '').upper()}")
        y -= 0.6 * cm
    
    c.setStrokeColor(colors.grey)
    c.setLineWidth(1)
    c.line(margin, y, width - margin, y)
    y -= 0.5 * cm
    
    # INSTRUCCIONES CORREGIDAS
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "INSTRUCCIONES:")
    y -= 0.35 * cm
    
    c.setFont("Helvetica", 8)
    instrucciones = [
        "• Marque A, B, C, D o E (en mayúsculas y solo una letra) dentro de los paréntesis",
        "• Solo una respuesta por pregunta",
        "• No realice borrones"
    ]
    
    for inst in instrucciones:
        c.drawString(margin + 0.3 * cm, y, inst)
        y -= 0.32 * cm
    
    y -= 0.3 * cm
    
    # GRID DE RESPUESTAS - CON LÍNEAS MEJORADAS
    preguntas_por_fila = 5
    espacio_pregunta = 3.3 * cm
    espacio_linea = 0.58 * cm  # Aumentado para más espacio
    
    x_inicial = margin + 0.2 * cm
    y_inicial = y
    
    for i in range(100):
        num_pregunta = i + 1
        fila = i // preguntas_por_fila
        columna = i % preguntas_por_fila
        
        x = x_inicial + (columna * espacio_pregunta)
        y_actual = y_inicial - (fila * espacio_linea)
        
        # Línea tenue ENTRE filas (no tocando paréntesis)
        if i > 0 and i % preguntas_por_fila == 0:
            c.setStrokeColor(colors.HexColor("#eeeeee"))  # Gris muy claro
            c.setLineWidth(0.3)
            # Línea JUSTO entre las dos filas
            y_linea = y_actual + (espacio_linea / 2) - 0.05*cm
            c.line(margin, y_linea, width - margin, y_linea)
            c.setStrokeColor(colors.black)
        
        # Número de pregunta
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(x + 0.7 * cm, y_actual, f"{num_pregunta}.")
        
        # Paréntesis
        c.setFont("Courier-Bold", 12)
        c.drawString(x + 0.8 * cm, y_actual - 0.05*cm, "(      )")
    
    # PIE DE PÁGINA
    y_footer = margin_bottom + 1.2 * cm
    
    if incluir_firma:
        c.setFont("Helvetica", 7)
        c.drawString(margin, y_footer + 0.4 * cm, "FIRMA DEL PROFESOR RESPONSABLE:")
        c.setLineWidth(0.5)
        c.line(margin + 5.5 * cm, y_footer + 0.3 * cm, 
               margin + 10 * cm, y_footer + 0.3 * cm)
        
        c.drawString(width - margin - 4.5 * cm, y_footer + 0.4 * cm, "FECHA:")
        c.line(width - margin - 3 * cm, y_footer + 0.3 * cm, 
               width - margin, y_footer + 0.3 * cm)
    
    c.setFont("Helvetica", 6)
    c.setFillColor(colors.grey)
    c.drawString(margin, margin_bottom + 0.3 * cm, 
                 f"Proceso: {proceso_admision} | Hoja: {codigo_hoja}")
    
    c.save()

# ============================================================================
# ENDPOINT DE GENERACIÓN
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
    proceso_admision: str = Form("2025-1")
):
    """
    Genera hojas de respuestas en PDF
    """
    db = SessionLocal()
    
    try:
        postulantes_data = []
        
        if tipo == "todos":
            postulantes = db.query(Postulante).all()
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,  # DNI es el código
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
            
            postulantes_data.append({
                "codigo": postulante.dni,
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
            for p in postulantes:
                postulantes_data.append({
                    "codigo": p.dni,
                    "datos": {
                        "dni": p.dni,
                        "nombres": p.nombres,
                        "apellido_paterno": p.apellido_paterno,
                        "apellido_materno": p.apellido_materno,
                        "programa": p.programa_educativo
                    } if incluir_datos else None
                })
                
        elif tipo == "sin_identificar":
            for i in range(cantidad_hojas):
                postulantes_data.append({
                    "codigo": f"SIN-ID-{i+1:04d}",
                    "datos": None
                })
        
        # Generar PDFs
        temp_dir = tempfile.mkdtemp()
        pdf_files = []
        
        for item in postulantes_data:
            filename = f"hoja_dni_{item['codigo']}.pdf"
            filepath = os.path.join(temp_dir, filename)
            
            generar_hoja_respuesta_pdf(
                output_path=filepath,
                codigo_postulante=item['codigo'],
                datos_postulante=item['datos'],
                proceso_admision=proceso_admision,
                incluir_firma=incluir_firma
            )
            
            pdf_files.append(filepath)
        
        # Crear ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for pdf_file in pdf_files:
                zip_file.write(pdf_file, os.path.basename(pdf_file))
        
        zip_buffer.seek(0)
        
        # Limpiar archivos temporales
        for pdf_file in pdf_files:
            os.remove(pdf_file)
        os.rmdir(temp_dir)
        
        # Retornar ZIP
        filename = f"hojas_respuestas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    finally:
        db.close()


# ============================================================================
# FUNCIÓN: VALIDAR CÓDIGOS
# ============================================================================

def validar_codigos(dni_postulante: str, dni_profesor: str, codigo_aula: str, db):
    """
    Valida que los códigos existan en la base de datos
    Retorna: (estado, mensajes, datos_validados)
    """
    errores = []
    mensajes = []
    datos = {
        "postulante": None,
        "profesor": None,
        "aula": None
    }
    
    # Validar DNI postulante
    postulante = db.query(Postulante).filter_by(dni=dni_postulante).first()
    if not postulante:
        errores.append("DNI_POSTULANTE")
        mensajes.append(f"⚠️ DNI postulante {dni_postulante} no registrado")
    else:
        datos["postulante"] = postulante
    
    # Validar DNI profesor
    profesor = db.query(Profesor).filter_by(dni=dni_profesor).first()
    if not profesor:
        errores.append("DNI_PROFESOR")
        mensajes.append(f"⚠️ DNI profesor {dni_profesor} no registrado")
    else:
        datos["profesor"] = profesor
    
    # Validar código aula
    aula = db.query(Aula).filter_by(codigo=codigo_aula).first()
    if not aula:
        errores.append("CODIGO_AULA")
        mensajes.append(f"⚠️ Código aula {codigo_aula} no existe")
    else:
        datos["aula"] = aula
    
    # Determinar estado
    if len(errores) == 0:
        estado = "completado"
        mensajes = ["✅ Hoja validada correctamente"]
    elif len(errores) >= 2:
        estado = "error"
        mensajes.insert(0, "🚨 ALERTA: Múltiples códigos incorrectos")
    else:
        estado = "observado"
    
    return estado, mensajes, datos

# ============================================================================
# FUNCIÓN: GUARDAR FOTO TEMPORALMENTE
# ============================================================================

def guardar_foto_temporal(file: UploadFile) -> tuple:
    """
    Guarda la foto temporalmente en el servidor
    Retorna: (filepath, filename)
    """
    # Crear directorio temporal si no existe
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    # Generar nombre único
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = temp_dir / filename
    
    # Guardar archivo
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return str(filepath), filename

# ============================================================================
# ENDPOINT: CAPTURAR HOJA
# ============================================================================

@app.post("/api/capturar-hoja")
async def capturar_hoja(
    file: UploadFile = File(...),
    dni_postulante: str = Form(...),
    dni_profesor: str = Form(...),
    codigo_aula: str = Form(...),
    proceso_admision: str = Form("2025-1")
):
    """
    Endpoint para capturar hojas de respuestas con validación
    """
    db = SessionLocal()
    inicio = time.time()
    
    try:
        # 1. VALIDAR CÓDIGOS
        estado, mensajes, datos = validar_codigos(
            dni_postulante, dni_profesor, codigo_aula, db
        )
        
        # 2. GENERAR CÓDIGO ÚNICO DE HOJA
        codigo_hoja = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        
        # 3. GUARDAR FOTO TEMPORALMENTE
        filepath, filename = guardar_foto_temporal(file)
        
        # 4. CREAR REGISTRO EN BD
        hoja = HojaRespuesta(
            postulante_id=datos["postulante"].id if datos["postulante"] else None,
            dni_profesor=dni_profesor,
            codigo_aula=codigo_aula,
            codigo_hoja=codigo_hoja,
            proceso_admision=proceso_admision,
            imagen_url=filepath,
            imagen_original_nombre=filename,
            estado=estado,
            observaciones=", ".join(mensajes) if len(mensajes) > 1 else mensajes[0]
        )
        
        db.add(hoja)
        db.commit()
        db.refresh(hoja)
        
        tiempo_total = time.time() - inicio
        
        # 5. RESPUESTA INMEDIATA
        return {
            "success": True,
            "id": hoja.id,
            "codigo_hoja": codigo_hoja,
            "estado": estado,
            "mensajes": mensajes,
            "tiempo": f"{tiempo_total:.2f}s",
            "postulante": {
                "id": datos["postulante"].id,
                "nombres": f"{datos['postulante'].apellido_paterno} {datos['postulante'].apellido_materno}, {datos['postulante'].nombres}",
                "programa": datos["postulante"].programa_educativo,
                "dni": dni_postulante
            } if datos["postulante"] else None,
            "profesor": {
                "nombres": f"{datos['profesor'].apellido_paterno} {datos['profesor'].apellido_materno}, {datos['profesor'].nombres}"
            } if datos["profesor"] else None,
            "aula": {
                "codigo": codigo_aula,
                "nombre": datos["aula"].nombre
            } if datos["aula"] else None
        }
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# ============================================================================
# ENDPOINT: REGISTRAR GABARITO MANUAL
# ============================================================================

@app.post("/api/registrar-gabarito-manual")
async def registrar_gabarito_manual(
    respuestas: str = Form(...),
    proceso_admision: str = Form("2025-1")
):
    """
    Registra las respuestas correctas manualmente
    """
    db = SessionLocal()
    
    try:
        # Convertir string a lista
        lista_respuestas = [r.strip().upper() for r in respuestas.split(",")]
        
        # Validar que sean 100 respuestas
        if len(lista_respuestas) != 100:
            raise HTTPException(
                status_code=400, 
                detail=f"Se esperan 100 respuestas, se recibieron {len(lista_respuestas)}"
            )
        
        # Validar que todas sean A, B, C, D o E
        validas = set(['A', 'B', 'C', 'D', 'E'])
        for i, resp in enumerate(lista_respuestas, 1):
            if resp not in validas:
                raise HTTPException(
                    status_code=400,
                    detail=f"Respuesta {i} inválida: '{resp}'. Debe ser A, B, C, D o E"
                )
        
        # Borrar gabarito anterior del mismo proceso
        from app.models.clave_respuesta import ClaveRespuesta
        db.query(ClaveRespuesta).filter_by(proceso_admision=proceso_admision).delete()
        
        # Insertar nuevas respuestas correctas
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
            "total_respuestas": len(lista_respuestas),
            "vista_previa": {
                "primeras_10": lista_respuestas[:10],
                "ultimas_10": lista_respuestas[-10:]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================================================
# AGREGAR ESTE CÓDIGO A app/main.py (AL FINAL, ANTES DE if __name__)
# ============================================================================

import anthropic
import os
import base64
import json
from typing import List, Dict

# ============================================================================
# FUNCIÓN: PROCESAR IMAGEN CON CLAUDE
# ============================================================================

async def procesar_imagen_con_claude(imagen_path: str) -> Dict:
    """
    Procesa una imagen de hoja de respuestas usando Claude API
    
    Args:
        imagen_path: Ruta local de la imagen
        
    Returns:
        Dict con respuestas extraídas y metadata
    """
    try:
        # Leer imagen y convertir a base64
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        # Detectar tipo de imagen
        ext = imagen_path.split(".")[-1].lower()
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        
        # Inicializar cliente de Anthropic
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        
        # Prompt para Claude
        prompt = """Analiza esta hoja de respuestas de examen de admisión.

La hoja contiene 100 preguntas numeradas del 1 al 100.
Cada pregunta tiene un paréntesis donde el estudiante escribió UNA letra: A, B, C, D o E.

INSTRUCCIONES:
1. Identifica TODAS las 100 respuestas marcadas
2. Si una respuesta está vacía, usa null
3. Si no puedes leer una respuesta con seguridad, usa null
4. Retorna SOLO un JSON válido, sin texto adicional

FORMATO DE RESPUESTA (JSON):
{
  "respuestas": ["A", "B", "C", "D", "E", "A", null, "C", ...],
  "confianza_promedio": 0.95,
  "respuestas_detectadas": 98,
  "respuestas_vacias": 2,
  "notas": "Observaciones si hay alguna dificultad en la lectura"
}

IMPORTANTE: 
- El array "respuestas" debe tener EXACTAMENTE 100 elementos
- Usa null para respuestas vacías o ilegibles
- Solo letras mayúsculas: A, B, C, D, E
- NO agregues texto fuera del JSON"""

        # Llamada a Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )
        
        # Extraer respuesta
        respuesta_texto = message.content[0].text
        
        # Limpiar respuesta (por si Claude agregó markdown)
        respuesta_texto = respuesta_texto.strip()
        if respuesta_texto.startswith("```json"):
            respuesta_texto = respuesta_texto[7:]
        if respuesta_texto.startswith("```"):
            respuesta_texto = respuesta_texto[3:]
        if respuesta_texto.endswith("```"):
            respuesta_texto = respuesta_texto[:-3]
        respuesta_texto = respuesta_texto.strip()
        
        # Parsear JSON
        resultado = json.loads(respuesta_texto)
        
        # Validar estructura
        if "respuestas" not in resultado:
            raise ValueError("Respuesta de Claude no contiene el campo 'respuestas'")
        
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"Se esperaban 100 respuestas, se obtuvieron {len(resultado['respuestas'])}")
        
        return {
            "success": True,
            "respuestas": resultado["respuestas"],
            "confianza_promedio": resultado.get("confianza_promedio", 0.95),
            "respuestas_detectadas": resultado.get("respuestas_detectadas", 100),
            "respuestas_vacias": resultado.get("respuestas_vacias", 0),
            "notas": resultado.get("notas", ""),
            "tokens_usados": message.usage.input_tokens + message.usage.output_tokens
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Error al parsear JSON de Claude: {str(e)}",
            "respuesta_cruda": respuesta_texto if 'respuesta_texto' in locals() else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# FUNCIÓN: CALCULAR CALIFICACIÓN
# ============================================================================

def calcular_calificacion(respuestas_alumno: List, respuestas_correctas_db, db) -> Dict:
    """
    Calcula la nota comparando respuestas del alumno con el gabarito
    
    Args:
        respuestas_alumno: Lista de 100 respuestas del alumno
        respuestas_correctas_db: Query de ClaveRespuesta
        db: Sesión de base de datos
        
    Returns:
        Dict con correctas, incorrectas, vacias y nota
    """
    # Obtener gabarito ordenado
    gabarito = respuestas_correctas_db.order_by(ClaveRespuesta.numero_pregunta).all()
    
    if len(gabarito) != 100:
        raise ValueError(f"El gabarito debe tener 100 respuestas, tiene {len(gabarito)}")
    
    correctas = 0
    incorrectas = 0
    vacias = 0
    
    for i, resp_alumno in enumerate(respuestas_alumno):
        resp_correcta = gabarito[i].respuesta_correcta.upper()
        
        if resp_alumno is None or resp_alumno == "":
            vacias += 1
        elif resp_alumno.upper() == resp_correcta:
            correctas += 1
        else:
            incorrectas += 1
    
    # Nota sobre 20
    nota = (correctas / 100) * 20
    
    return {
        "correctas": correctas,
        "incorrectas": incorrectas,
        "vacias": vacias,
        "nota": round(nota, 2)
    }

# ============================================================================
# ENDPOINT: PROCESAR HOJA CON CLAUDE
# ============================================================================

# ============================================================================
# AGREGAR ESTE ENDPOINT A app/main.py (REEMPLAZA /api/procesar-hoja)
# ============================================================================

@app.post("/api/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    metadata_captura: str = Form(None),
    image_hash: str = Form(None),
    request: Request = None
):
    """
    Endpoint COMPLETO que:
    1. Recibe la foto
    2. Claude extrae CÓDIGOS (DNI postulante, DNI profesor, código aula) + RESPUESTAS
    3. Valida códigos en BD
    4. Calcula nota
    5. Guarda todo con metadata de seguridad
    """
    db = SessionLocal()
    inicio = time.time()
    
    try:
        # 1. GUARDAR FOTO TEMPORALMENTE
        filepath, filename = guardar_foto_temporal(file)
        
        # 2. PARSEAR METADATA
        metadata = {}
        if metadata_captura:
            try:
                metadata = json.loads(metadata_captura)
            except:
                pass
        
        # Agregar IP del servidor
        if request:
            metadata['ip_address'] = request.client.host
        
        metadata['image_hash'] = image_hash
        metadata['filename_original'] = file.filename
        
        # 3. PROCESAR CON CLAUDE - EXTRAER TODO
        print("📸 Procesando imagen con Claude...")
        resultado_claude = await extraer_todo_con_claude(filepath)
        
        if not resultado_claude["success"]:
            raise HTTPException(status_code=500, detail=resultado_claude["error"])
        
        # 4. EXTRAER DATOS
        datos_extraidos = resultado_claude["datos"]
        dni_postulante = datos_extraidos.get("dni_postulante")
        dni_profesor = datos_extraidos.get("dni_profesor")
        codigo_aula = datos_extraidos.get("codigo_aula")
        codigo_hoja = datos_extraidos.get("codigo_hoja")
        proceso_admision = datos_extraidos.get("proceso_admision", "2025-1")
        respuestas_alumno = datos_extraidos.get("respuestas", [])
        
        print(f"✅ Extraído - DNI Postulante: {dni_postulante}, Profesor: {dni_profesor}, Aula: {codigo_aula}")
        
        # 5. VALIDAR CÓDIGOS EN BD
        estado, mensajes, datos_validados = validar_codigos(
            dni_postulante, dni_profesor, codigo_aula, db
        )
        
        # 6. OBTENER GABARITO
        gabarito_query = db.query(ClaveRespuesta).filter_by(
            proceso_admision=proceso_admision
        )
        
        if gabarito_query.count() == 0:
            raise HTTPException(
                status_code=400, 
                detail=f"No existe gabarito para el proceso {proceso_admision}"
            )
        
        # 7. CALCULAR NOTA
        calificacion = calcular_calificacion(respuestas_alumno, gabarito_query, db)
        
        # 8. GUARDAR HOJA EN BD
        hoja = HojaRespuesta(
            postulante_id=datos_validados["postulante"].id if datos_validados["postulante"] else None,
            dni_profesor=dni_profesor,
            codigo_aula=codigo_aula,
            codigo_hoja=codigo_hoja,
            proceso_admision=proceso_admision,
            imagen_url=filepath,
            imagen_original_nombre=filename,
            estado=estado,
            api_utilizada="anthropic",
            respuestas_detectadas=len([r for r in respuestas_alumno if r]),
            nota_final=calificacion["nota"],
            respuestas_correctas_count=calificacion["correctas"],
            tiempo_procesamiento=time.time() - inicio,
            fecha_calificacion=datetime.utcnow(),
            observaciones=", ".join(mensajes),
            metadata_json=json.dumps({
                "captura": metadata,
                "claude": {
                    "confianza": resultado_claude.get("confianza_promedio", 0.95),
                    "tokens": resultado_claude.get("tokens_usados", 0)
                },
                "validacion": {
                    "estado": estado,
                    "mensajes": mensajes
                }
            })
        )
        
        db.add(hoja)
        db.commit()
        db.refresh(hoja)
        
        # 9. GUARDAR RESPUESTAS INDIVIDUALES
        gabarito = gabarito_query.order_by(ClaveRespuesta.numero_pregunta).all()
        for i, resp_alumno in enumerate(respuestas_alumno, 1):
            respuesta = Respuesta(
                hoja_respuesta_id=hoja.id,
                numero_pregunta=i,
                respuesta_marcada=resp_alumno if resp_alumno else None,
                es_correcta=(resp_alumno and resp_alumno.upper() == gabarito[i-1].respuesta_correcta.upper()),
                confianza=resultado_claude.get("confianza_promedio", 0.95)
            )
            db.add(respuesta)
        
        db.commit()
        
        tiempo_total = time.time() - inicio
        
        # 10. RESPUESTA
        postulante = datos_validados["postulante"]
        
        return {
            "success": True,
            "hoja_id": hoja.id,
            "codigo_hoja": codigo_hoja,
            "postulante": {
                "id": postulante.id,
                "dni": postulante.dni,
                "nombres": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa": postulante.programa_educativo
            } if postulante else {
                "dni": dni_postulante,
                "error": "DNI no encontrado en base de datos"
            },
            "profesor": {
                "dni": dni_profesor,
                "nombres": f"{datos_validados['profesor'].apellido_paterno} {datos_validados['profesor'].apellido_materno}, {datos_validados['profesor'].nombres}"
            } if datos_validados["profesor"] else {
                "dni": dni_profesor,
                "error": "DNI no encontrado"
            },
            "aula": {
                "codigo": codigo_aula,
                "nombre": datos_validados["aula"].nombre
            } if datos_validados["aula"] else {
                "codigo": codigo_aula,
                "error": "Aula no encontrada"
            },
            "calificacion": {
                "nota": calificacion["nota"],
                "correctas": calificacion["correctas"],
                "incorrectas": calificacion["incorrectas"],
                "vacias": calificacion["vacias"]
            },
            "procesamiento": {
                "api": "Claude Sonnet 4",
                "tiempo": f"{tiempo_total:.2f}s",
                "confianza": resultado_claude.get("confianza_promedio", 0.95),
                "tokens": resultado_claude.get("tokens_usados", 0)
            },
            "validacion": {
                "estado": estado,
                "mensajes": mensajes
            },
            "metadata": {
                "gps": metadata.get("gps"),
                "timestamp": metadata.get("timestamp"),
                "device": metadata.get("device_fingerprint")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================================================
# FUNCIÓN: EXTRAER TODO CON CLAUDE (CÓDIGOS + RESPUESTAS)
# ============================================================================

async def extraer_todo_con_claude(imagen_path: str) -> Dict:
    """
    Usa Claude para extraer:
    - DNI Postulante (8 dígitos de los cuadros superiores)
    - DNI Profesor (8 dígitos)
    - Código Aula (4 dígitos)
    - Código Hoja (alfanumérico 9 caracteres)
    - 100 respuestas (A, B, C, D, E)
    """
    try:
        # Leer imagen y convertir a base64
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        # Detectar tipo de imagen
        ext = imagen_path.split(".")[-1].lower()
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        
        # Inicializar cliente de Anthropic
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        
        # Prompt para Claude
        prompt = """Analiza esta hoja de respuestas de examen de admisión del INSTITUTO SUPERIOR TECNOLÓGICO SANTANA.

IMPORTANTE: La hoja tiene DOS secciones:

## SECCIÓN 1: CÓDIGOS EN LA PARTE SUPERIOR (en cuadros individuales)
- **DNI Alumno**: 8 dígitos en cuadros individuales
- **Código Aula**: 4 dígitos en cuadros individuales
- **DNI Profesor**: 8 dígitos en cuadros individuales
- **Código Hoja**: 9 caracteres alfanuméricos (ejemplo: "A2iDñ5RsW") que dice "Hoja: XXXXXXXXX"

## SECCIÓN 2: RESPUESTAS (100 preguntas numeradas)
Cada pregunta tiene un paréntesis con UNA letra: A, B, C, D o E.

INSTRUCCIONES:
1. Lee TODOS los códigos de los cuadros superiores
2. Lee las 100 respuestas de los paréntesis
3. Si una respuesta está vacía, usa null
4. Si no puedes leer algo con seguridad, usa null
5. Retorna SOLO un JSON válido, sin texto adicional

FORMATO DE RESPUESTA (JSON):
{
  "dni_postulante": "12345678",
  "dni_profesor": "87654321",
  "codigo_aula": "A101",
  "codigo_hoja": "A2iDñ5RsW",
  "proceso_admision": "2025-1",
  "respuestas": ["A", "B", "C", "D", "E", null, "A", ...],
  "confianza_promedio": 0.95,
  "respuestas_detectadas": 98,
  "notas": "Observaciones si hay dificultad"
}

CRÍTICO:
- DNI postulante: 8 dígitos NUMÉRICOS
- DNI profesor: 8 dígitos NUMÉRICOS
- Código aula: texto/números (ej: "A101", "B205")
- Código hoja: 9 caracteres alfanuméricos
- Respuestas: array de EXACTAMENTE 100 elementos
- Solo letras mayúsculas: A, B, C, D, E o null"""

        # Llamada a Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )
        
        # Extraer respuesta
        respuesta_texto = message.content[0].text
        
        # Limpiar respuesta
        respuesta_texto = respuesta_texto.strip()
        if respuesta_texto.startswith("```json"):
            respuesta_texto = respuesta_texto[7:]
        if respuesta_texto.startswith("```"):
            respuesta_texto = respuesta_texto[3:]
        if respuesta_texto.endswith("```"):
            respuesta_texto = respuesta_texto[:-3]
        respuesta_texto = respuesta_texto.strip()
        
        # Parsear JSON
        resultado = json.loads(respuesta_texto)
        
        # Validar estructura
        required_fields = ["dni_postulante", "dni_profesor", "codigo_aula", "respuestas"]
        for field in required_fields:
            if field not in resultado:
                raise ValueError(f"Respuesta de Claude no contiene el campo '{field}'")
        
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"Se esperaban 100 respuestas, se obtuvieron {len(resultado['respuestas'])}")
        
        return {
            "success": True,
            "datos": resultado,
            "confianza_promedio": resultado.get("confianza_promedio", 0.95),
            "tokens_usados": message.usage.input_tokens + message.usage.output_tokens
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Error al parsear JSON de Claude: {str(e)}",
            "respuesta_cruda": respuesta_texto if 'respuesta_texto' in locals() else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# ENDPOINT: OBTENER RESULTADOS (RANKING)
# ============================================================================

@app.get("/api/resultados/{proceso_admision}")
async def obtener_resultados(proceso_admision: str):
    """
    Obtiene el ranking de postulantes de un proceso específico
    """
    db = SessionLocal()
    
    try:
        # Obtener hojas procesadas del proceso
        hojas = db.query(HojaRespuesta).filter(
            HojaRespuesta.proceso_admision == proceso_admision,
            HojaRespuesta.estado == "completado",
            HojaRespuesta.nota_final.isnot(None)
        ).order_by(HojaRespuesta.nota_final.desc()).all()
        
        resultados = []
        for i, hoja in enumerate(hojas, 1):
            postulante = db.query(Postulante).filter_by(id=hoja.postulante_id).first()
            if postulante:
                resultados.append({
                    "puesto": i,
                    "dni": postulante.dni,
                    "nombres": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                    "programa": postulante.programa_educativo,
                    "nota": hoja.nota_final,
                    "correctas": hoja.respuestas_correctas_count,
                    "codigo_hoja": hoja.codigo_hoja,
                    "fecha_examen": hoja.fecha_captura.isoformat() if hoja.fecha_captura else None
                })
        
        return {
            "success": True,
            "proceso": proceso_admision,
            "total_postulantes": len(resultados),
            "resultados": resultados
        }
        
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)