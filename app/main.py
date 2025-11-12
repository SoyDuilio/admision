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
from datetime import datetime, timezone
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



# ============================================================================
# EXTRACCIÓN CON CLAUDE (Anthropic)
# ============================================================================

async def extraer_con_claude(imagen_path: str) -> Dict:
    """
    Extrae datos con Claude Vision.
    """
    try:
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        ext = imagen_path.split(".")[-1].lower()
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        prompt = """Analiza esta hoja de respuestas de examen de admisión.

ESTRUCTURA:

## CÓDIGOS (en la parte superior, 2 líneas):
LÍNEA 1 (labels): DNI Postulante    Código Aula    DNI Profesor
LÍNEA 2 (valores): Debajo de cada label están los códigos correspondientes, separados por espacios.

Encontrarás 3 bloques de códigos separados por espacios:
- Los primeros 8 dígitos consecutivos: DNI del Postulante
- Los siguientes 4-5 caracteres consecutivos: Código del Aula (puede tener letras y números)
- Los últimos 8 dígitos consecutivos: DNI del Profesor

Ejemplo:
DNI Postulante              Código Aula         DNI Profesor
70123456                    C201                12345678

Después hay una línea que dice "Código de Hoja:" seguido de un código alfanumérico de 9 caracteres (sin i, l, o, 0, 1).

## RESPUESTAS (100 preguntas numeradas del 1 al 100):
Cada pregunta tiene formato: N. (  )
Donde N es el número de pregunta y dentro del paréntesis hay UNA letra: A, B, C, D o E.

REGLAS:
1. DEBES retornar EXACTAMENTE 100 elementos en "respuestas"
2. Si el paréntesis está VACÍO → usa null
3. Si hay una letra válida (A, B, C, D, E) → úsala en MAYÚSCULA
4. Si hay minúscula (a,b,c,d,e) → convierte a MAYÚSCULA
5. Cualquier otro valor → usa null

RESPONDE SOLO CON ESTE JSON:
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-1",
  "respuestas": ["A", "B", null, "C", "D", ...]
}

VALIDACIÓN: Verifica que "respuestas" tenga EXACTAMENTE 100 elementos."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        respuesta_texto = message.content[0].text.strip()
        if respuesta_texto.startswith("```json"):
            respuesta_texto = respuesta_texto[7:]
        if respuesta_texto.startswith("```"):
            respuesta_texto = respuesta_texto[3:]
        if respuesta_texto.endswith("```"):
            respuesta_texto = respuesta_texto[:-3]
        respuesta_texto = respuesta_texto.strip()
        
        resultado = json.loads(respuesta_texto)
        
        # Validar
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"Se esperaban 100 respuestas, se obtuvieron {len(resultado['respuestas'])}")
        
        # Normalizar respuestas
        respuestas_validadas = []
        for resp in resultado["respuestas"]:
            if resp is None or resp == "":
                respuestas_validadas.append(None)
            elif isinstance(resp, str) and resp.strip().upper() in ["A", "B", "C", "D", "E"]:
                respuestas_validadas.append(resp.strip().upper())
            else:
                respuestas_validadas.append(None)
        
        resultado["respuestas"] = respuestas_validadas
        
        return {
            "success": True,
            "api": "claude",
            "datos": resultado,
            "tokens": message.usage.input_tokens + message.usage.output_tokens
        }
        
    except Exception as e:
        return {"success": False, "api": "claude", "error": str(e)}


# ============================================================================
# EXTRACCIÓN CON GOOGLE VISION
# ============================================================================

async def extraer_con_google_vision(imagen_path: str) -> Dict:
    """
    Extrae datos con Google Vision API + Gemini.
    """
    try:
        # Inicializar cliente
        # Requiere: pip install google-cloud-vision google-generativeai
        from google.cloud import vision
        import google.generativeai as genai
        
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        # Leer imagen
        with open(imagen_path, "rb") as image_file:
            content = image_file.read()
        
        # OCR con Vision
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        
        if response.error.message:
            raise Exception(response.error.message)
        
        texto_ocr = response.text_annotations[0].description if response.text_annotations else ""
        
        # Procesar con Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Analiza este texto extraído de una hoja de examen:

{texto_ocr}

Extrae:
1. DNI Postulante (8 dígitos, primeros en aparecer después de "DNI Postulante")
2. Código Aula (4-5 caracteres, aparece después de "Código Aula")
3. DNI Profesor (8 dígitos, aparece después de "DNI Profesor")
4. Código Hoja (9 caracteres alfanuméricos, aparece después de "Código de Hoja:")
5. 100 respuestas (busca números del 1 al 100 seguidos de paréntesis con letras A,B,C,D,E o vacíos)

RESPONDE SOLO JSON:
{{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-1",
  "respuestas": ["A", "B", null, ...]
}}

CRÍTICO: "respuestas" debe tener EXACTAMENTE 100 elementos."""

        response = model.generate_content(prompt)
        resultado_texto = response.text.strip()
        
        # Limpiar JSON
        if resultado_texto.startswith("```json"):
            resultado_texto = resultado_texto[7:]
        if resultado_texto.startswith("```"):
            resultado_texto = resultado_texto[3:]
        if resultado_texto.endswith("```"):
            resultado_texto = resultado_texto[:-3]
        resultado_texto = resultado_texto.strip()
        
        resultado = json.loads(resultado_texto)
        
        # Validar 100 respuestas
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"Google Vision: {len(resultado['respuestas'])} respuestas en lugar de 100")
        
        return {
            "success": True,
            "api": "google_vision",
            "datos": resultado
        }
        
    except Exception as e:
        return {"success": False, "api": "google_vision", "error": str(e)}


# ============================================================================
# EXTRACCIÓN CON OPENAI GPT-4 VISION
# ============================================================================

async def extraer_con_openai(imagen_path: str) -> Dict:
    """
    Extrae datos con OpenAI GPT-4 Vision.
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Leer imagen
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        prompt = """Analiza esta hoja de respuestas de examen.

CÓDIGOS (parte superior):
- DNI Postulante: 8 dígitos (primera línea de números)
- Código Aula: 4-5 caracteres alfanuméricos (entre DNI Postulante y DNI Profesor)
- DNI Profesor: 8 dígitos (última línea de números)
- Código Hoja: 9 caracteres alfanuméricos (después de "Código de Hoja:")

RESPUESTAS:
- 100 preguntas numeradas 1-100
- Cada una tiene formato: N. (  )
- Dentro del paréntesis puede haber: A, B, C, D, E o estar vacío

RESPONDE SOLO JSON:
{
  "dni_postulante": "70123456",
  "codigo_aula": "C201",
  "dni_profesor": "12345678",
  "codigo_hoja": "ABC23456D",
  "proceso_admision": "2025-1",
  "respuestas": ["A", null, "B", ...]
}

IMPORTANTE: Array "respuestas" debe tener EXACTAMENTE 100 elementos."""

        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            }],
            max_tokens=4000,
            temperature=0
        )
        
        resultado_texto = response.choices[0].message.content.strip()
        
        # Limpiar JSON
        if resultado_texto.startswith("```json"):
            resultado_texto = resultado_texto[7:]
        if resultado_texto.startswith("```"):
            resultado_texto = resultado_texto[3:]
        if resultado_texto.endswith("```"):
            resultado_texto = resultado_texto[:-3]
        resultado_texto = resultado_texto.strip()
        
        resultado = json.loads(resultado_texto)
        
        # Validar
        if len(resultado["respuestas"]) != 100:
            raise ValueError(f"OpenAI: {len(resultado['respuestas'])} respuestas en lugar de 100")
        
        return {
            "success": True,
            "api": "openai",
            "datos": resultado,
            "tokens": response.usage.total_tokens
        }
        
    except Exception as e:
        return {"success": False, "api": "openai", "error": str(e)}


# ============================================================================
# FUNCIÓN PRINCIPAL: PROBAR CON LAS 3 APIS
# ============================================================================

async def extraer_con_todas_las_apis(imagen_path: str):
    """
    Prueba extracción con las 3 APIs y retorna la mejor.
    """
    resultados = []
    
    # Claude
    print("🔄 Probando con Claude...")
    resultado_claude = await extraer_con_claude(imagen_path)
    resultados.append(resultado_claude)
    
    # Google Vision
    print("🔄 Probando con Google Vision...")
    resultado_google = await extraer_con_google_vision(imagen_path)
    resultados.append(resultado_google)
    
    # OpenAI
    print("🔄 Probando con OpenAI...")
    resultado_openai = await extraer_con_openai(imagen_path)
    resultados.append(resultado_openai)
    
    # Analizar resultados
    exitosos = [r for r in resultados if r["success"]]
    
    if not exitosos:
        return {
            "success": False,
            "error": "Ninguna API pudo procesar la imagen",
            "intentos": resultados
        }
    
    # Retornar el primero exitoso (prioridad: Claude > OpenAI > Google)
    return exitosos[0]



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
# GENERADOR DE CÓDIGO ÚNICO (sin caracteres ambiguos)
# ============================================================================

def generar_codigo_hoja_unico():
    """
    Genera código alfanumérico de 9 caracteres.
    Excluye: i, l, I, L, o, O, 0, 1 (caracteres confusos)
    """
    # Caracteres seguros
    letras_seguras = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz'  # Sin i,l,o
    numeros_seguros = '23456789'  # Sin 0, 1
    
    # Formato: 3 letras + 5 números + 1 letra
    codigo = (
        ''.join(random.choices(letras_seguras.upper(), k=3)) +
        ''.join(random.choices(numeros_seguros, k=5)) +
        ''.join(random.choices(letras_seguras.upper(), k=1))
    )
    
    return codigo


# ============================================================================
# GENERADOR DE HOJAS DE RESPUESTAS
# ============================================================================

# ============================================================================
# GENERADOR DE PDF - HOJA DE RESPUESTAS OPTIMIZADA
# ============================================================================

def generar_hoja_respuestas_pdf(
    output_path: str,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str = None,
    proceso: str = "2025-1"
):
    """
    Genera PDF optimizado para lectura por LLM.
    
    Características:
    - Área útil: 80% del A4 (168mm × 237mm)
    - Códigos en línea separados por espacios
    - Respuestas: 5 por fila, 20 filas
    - Altura de fila: 9mm (óptima para cámara y LLM)
    """
    
    # Generar código si no se proporciona
    if not codigo_hoja:
        codigo_hoja = generar_codigo_hoja_unico()
    
    # Crear canvas
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # ========================================================================
    # ÁREA ÚTIL: 80% centrado
    # ========================================================================
    margen_h = width * 0.10  # 10% cada lado
    margen_v = height * 0.10  # 10% arriba y abajo
    
    area_width = width * 0.80
    area_height = height * 0.80
    
    x_start = margen_h
    y_start = height - margen_v
    
    # Marco del área útil (para visualización durante desarrollo)
    # c.setStrokeColor(colors.lightgrey)
    # c.rect(x_start, margen_v, area_width, area_height)
    
    # ========================================================================
    # ENCABEZADO
    # ========================================================================
    y = y_start
    
    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, y, "I. S. T. Pedro A. Del Águila H.")
    y -= 6*mm
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, y, f"EXAMEN DE ADMISIÓN - Proceso {proceso}")
    y -= 10*mm
    
    # Línea separadora
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(x_start, y, x_start + area_width, y)
    y -= 8*mm
    
    # ========================================================================
    # SECCIÓN CÓDIGOS (OPTIMIZADA PARA LLM)
    # ========================================================================
    
    # Etiquetas (labels)
    c.setFont("Helvetica-Bold", 10)
    
    # Calcular posiciones para 3 columnas centradas
    col_width = area_width / 3
    col1_x = x_start + col_width * 0.5
    col2_x = x_start + col_width * 1.5
    col3_x = x_start + col_width * 2.5
    
    c.drawCentredString(col1_x, y, "DNI Postulante")
    c.drawCentredString(col2_x, y, "Código Aula")
    c.drawCentredString(col3_x, y, "DNI Profesor")
    y -= 6*mm
    
    # Valores (con mayor tamaño y negrita)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(col1_x, y, dni_postulante)
    c.drawCentredString(col2_x, y, codigo_aula)
    c.drawCentredString(col3_x, y, dni_profesor)
    y -= 8*mm
    
    # Código de hoja (centrado, muy visible)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width/2, y, "Código de Hoja:")
    y -= 5*mm
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, y, codigo_hoja)
    y -= 10*mm
    
    # Línea separadora
    c.setLineWidth(1)
    c.line(x_start, y, x_start + area_width, y)
    y -= 8*mm
    
    # ========================================================================
    # INSTRUCCIONES
    # ========================================================================
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_start, y, "INSTRUCCIONES: Escriba UNA letra (A, B, C, D o E) dentro de cada paréntesis")
    y -= 8*mm
    
    # ========================================================================
    # RESPUESTAS: 5 por fila, 20 filas = 100 preguntas
    # ========================================================================
    
    c.setFont("Helvetica", 10)
    
    # Dimensiones óptimas
    fila_altura = 9*mm  # Altura generosa para cámara
    col_ancho = area_width / 5  # 5 columnas
    parentesis_ancho = 12*mm  # Ancho del paréntesis
    
    pregunta_num = 1
    
    for fila in range(20):  # 20 filas
        x = x_start
        
        for col in range(5):  # 5 columnas
            # Número de pregunta
            c.setFont("Helvetica-Bold", 10)
            num_text = f"{pregunta_num}."
            c.drawString(x, y, num_text)
            
            # Paréntesis
            c.setFont("Helvetica", 12)
            paren_x = x + 12*mm
            c.drawString(paren_x, y, "(     )")
            
            pregunta_num += 1
            x += col_ancho
        
        y -= fila_altura
        
        # Si se acaba el espacio, advertir
        if y < margen_v + 20*mm:
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(colors.red)
            c.drawString(x_start, y, "⚠️ Espacio insuficiente - ajustar diseño")
            break
    
    # ========================================================================
    # PIE DE PÁGINA
    # ========================================================================
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    pie_y = margen_v - 5*mm
    c.drawCentredString(width/2, pie_y, f"Código: {codigo_hoja} | Proceso: {proceso}")
    
    # Guardar PDF
    c.save()
    
    return {
        "success": True,
        "codigo_hoja": codigo_hoja,
        "filepath": output_path
    }


# ============================================================================
# ENDPOINT: GENERAR HOJAS PARA EXAMEN
# ============================================================================

@app.post("/api/generar-hojas-examen")
async def generar_hojas_examen(
    proceso_admision: str = "2025-1",
    cantidad: int = None,
    postulantes_ids: list = None
):
    """
    Genera hojas de respuestas pre-impresas para el examen.
    
    Crea:
    1. Registros en BD con códigos únicos
    2. PDFs individuales por postulante
    3. Estado: "generada"
    """
    db = SessionLocal()
    
    try:
        # Obtener postulantes
        if postulantes_ids:
            postulantes = db.query(Postulante).filter(
                Postulante.id.in_(postulantes_ids)
            ).all()
        elif cantidad:
            postulantes = db.query(Postulante).limit(cantidad).all()
        else:
            raise HTTPException(status_code=400, detail="Debe especificar 'cantidad' o 'postulantes_ids'")
        
        if not postulantes:
            raise HTTPException(status_code=404, detail="No se encontraron postulantes")
        
        hojas_generadas = []
        
        for postulante in postulantes:
            # Generar código único
            codigo_hoja = generar_codigo_hoja_unico()
            
            # Verificar que sea único
            while db.query(HojaRespuesta).filter_by(codigo_hoja=codigo_hoja).first():
                codigo_hoja = generar_codigo_hoja_unico()
            
            # Obtener aula asignada (ejemplo)
            # TODO: Implementar lógica de asignación de aulas
            codigo_aula = "A101"  # Por defecto
            dni_profesor = "00000000"  # Se llenará después
            
            # Generar PDF
            pdf_path = f"hojas_generadas/{codigo_hoja}.pdf"
            os.makedirs("hojas_generadas", exist_ok=True)
            
            resultado_pdf = generar_hoja_respuestas_pdf(
                output_path=pdf_path,
                dni_postulante=postulante.dni,
                codigo_aula=codigo_aula,
                dni_profesor=dni_profesor,
                codigo_hoja=codigo_hoja,
                proceso=proceso_admision
            )
            
            # Crear registro en BD
            hoja = HojaRespuesta(
                postulante_id=postulante.id,
                dni_profesor=dni_profesor,
                codigo_aula=codigo_aula,
                codigo_hoja=codigo_hoja,
                proceso_admision=proceso_admision,
                imagen_url=pdf_path,
                estado="generada",
                api_utilizada=None,
                fecha_generacion=datetime.now(timezone.utc)
            )
            
            db.add(hoja)
            hojas_generadas.append({
                "postulante": f"{postulante.nombres} {postulante.apellido_paterno}",
                "dni": postulante.dni,
                "codigo_hoja": codigo_hoja,
                "pdf": pdf_path
            })
        
        db.commit()
        
        return {
            "success": True,
            "total_generadas": len(hojas_generadas),
            "hojas": hojas_generadas
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



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

# ============================================================================
# ENDPOINT CORREGIDO - NO REQUIERE GABARITO
# ============================================================================

@app.post("/api/procesar-hoja-completa")
async def procesar_hoja_completa(
    file: UploadFile = File(...),
    metadata_captura: str = Form(None),
    image_hash: str = Form(None),
    request: Request = None
):
    """
    Endpoint que:
    1. Extrae códigos + respuestas con Claude
    2. Valida códigos en BD
    3. Guarda hoja con estado "pendiente_calificacion"
    4. NO requiere gabarito (se califica después)
    """
    db = SessionLocal()
    inicio = time.time()
    
    try:
        # 1. GUARDAR FOTO
        filepath, filename = guardar_foto_temporal(file)
        
        # 2. PARSEAR METADATA
        metadata = {}
        if metadata_captura:
            try:
                metadata = json.loads(metadata_captura)
            except:
                pass
        
        if request:
            metadata['ip_address'] = request.client.host
        
        metadata['image_hash'] = image_hash
        metadata['filename_original'] = file.filename
        
        # 3. PROCESAR CON CLAUDE
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
        
        print(f"✅ Extraído - DNI: {dni_postulante}, Profesor: {dni_profesor}, Aula: {codigo_aula}")
        
        # 5. VALIDAR CÓDIGOS
        estado, mensajes, datos_validados = validar_codigos(
            dni_postulante, dni_profesor, codigo_aula, db
        )
        
        # 6. VERIFICAR SI EXISTE GABARITO (pero NO es obligatorio)
        gabarito_existe = db.query(ClaveRespuesta).filter_by(
            proceso_admision=proceso_admision
        ).count() > 0
        
        if gabarito_existe:
            # Calificar inmediatamente
            gabarito_query = db.query(ClaveRespuesta).filter_by(
                proceso_admision=proceso_admision
            )
            calificacion = calcular_calificacion(respuestas_alumno, gabarito_query, db)
            nota_final = calificacion["nota"]
            correctas_count = calificacion["correctas"]
            estado_hoja = "completado"
            mensajes.append("✅ Hoja calificada automáticamente")
        else:
            # Guardar sin calificar
            nota_final = None
            correctas_count = None
            estado_hoja = "pendiente_calificacion"
            mensajes.append("⏳ Hoja guardada, pendiente de calificación")
        
        # 7. GUARDAR HOJA EN BD
        hoja = HojaRespuesta(
            postulante_id=datos_validados["postulante"].id if datos_validados["postulante"] else None,
            dni_profesor=dni_profesor,
            codigo_aula=codigo_aula,
            codigo_hoja=codigo_hoja,
            proceso_admision=proceso_admision,
            imagen_url=filepath,
            imagen_original_nombre=filename,
            estado=estado_hoja,
            api_utilizada="anthropic",
            respuestas_detectadas=len([r for r in respuestas_alumno if r]),
            nota_final=nota_final,
            respuestas_correctas_count=correctas_count,
            tiempo_procesamiento=time.time() - inicio,
            fecha_calificacion=datetime.now(timezone.utc) if gabarito_existe else None,
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
        
        # 8. GUARDAR RESPUESTAS INDIVIDUALES
        for i, resp_alumno in enumerate(respuestas_alumno, 1):
            respuesta = Respuesta(
                hoja_respuesta_id=hoja.id,
                numero_pregunta=i,
                respuesta_marcada=resp_alumno if resp_alumno else None,
                es_correcta=None,  # Se calculará después cuando exista gabarito
                confianza=resultado_claude.get("confianza_promedio", 0.95)
            )
            db.add(respuesta)
        
        db.commit()
        
        tiempo_total = time.time() - inicio
        postulante = datos_validados["postulante"]
        
        # 9. RESPUESTA
        response_data = {
            "success": True,
            "hoja_id": hoja.id,
            "codigo_hoja": codigo_hoja,
            "estado": estado_hoja,
            "postulante": {
                "id": postulante.id,
                "dni": postulante.dni,
                "nombres": f"{postulante.apellido_paterno} {postulante.apellido_materno}, {postulante.nombres}",
                "programa": postulante.programa_educativo
            } if postulante else {
                "dni": dni_postulante,
                "error": "DNI no encontrado"
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
        
        # Agregar calificación SOLO si existe gabarito
        if gabarito_existe:
            response_data["calificacion"] = {
                "nota": calificacion["nota"],
                "correctas": calificacion["correctas"],
                "incorrectas": calificacion["incorrectas"],
                "vacias": calificacion["vacias"]
            }
        else:
            response_data["calificacion"] = None
            response_data["mensaje"] = "Hoja guardada exitosamente. Se calificará cuando se registre el gabarito."
        
        return response_data
        
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
# NUEVO ENDPOINT: CALIFICAR MASIVAMENTE
# ============================================================================

@app.post("/api/calificar-hojas-pendientes")
async def calificar_hojas_pendientes(proceso_admision: str = "2025-1"):
    """
    Califica todas las hojas con estado "pendiente_calificacion"
    después de que se haya registrado el gabarito.
    """
    db = SessionLocal()
    
    try:
        # Verificar que existe gabarito
        gabarito_query = db.query(ClaveRespuesta).filter_by(
            proceso_admision=proceso_admision
        )
        
        if gabarito_query.count() == 0:
            raise HTTPException(
                status_code=400, 
                detail=f"No existe gabarito para el proceso {proceso_admision}"
            )
        
        gabarito = gabarito_query.order_by(ClaveRespuesta.numero_pregunta).all()
        
        # Obtener hojas pendientes
        hojas_pendientes = db.query(HojaRespuesta).filter_by(
            estado="pendiente_calificacion",
            proceso_admision=proceso_admision
        ).all()
        
        if not hojas_pendientes:
            return {
                "success": True,
                "mensaje": "No hay hojas pendientes de calificación",
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
                
                # Calcular calificación
                calificacion = calcular_calificacion(respuestas_array, gabarito_query, db)
                
                # Actualizar hoja
                hoja.nota_final = calificacion["nota"]
                hoja.respuestas_correctas_count = calificacion["correctas"]
                hoja.estado = "completado"
                hoja.fecha_calificacion = datetime.now(timezone.utc)
                
                # Actualizar respuestas individuales
                for i, resp in enumerate(respuestas):
                    resp.es_correcta = (
                        resp.respuesta_marcada and 
                        resp.respuesta_marcada.upper() == gabarito[i].respuesta_correcta.upper()
                    )
                
                calificadas += 1
                
            except Exception as e:
                errores.append({
                    "hoja_id": hoja.id,
                    "error": str(e)
                })
        
        db.commit()
        
        return {
            "success": True,
            "mensaje": f"Proceso completado",
            "calificadas": calificadas,
            "total_pendientes": len(hojas_pendientes),
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
# FUNCIÓN: EXTRAER TODO CON CLAUDE (CÓDIGOS + RESPUESTAS)
# ============================================================================

async def extraer_todo_con_claude(imagen_path: str) -> Dict:
    """
    Usa Claude para extraer códigos + respuestas con VALIDACIÓN ESTRICTA.
    """
    try:
        # Leer imagen
        with open(imagen_path, "rb") as image_file:
            image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        
        ext = imagen_path.split(".")[-1].lower()
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        
        # ====================================================================
        # PROMPT MEJORADO - MUY ESTRICTO
        # ====================================================================
        prompt = """Analiza esta hoja de respuestas de examen de admisión del I. S. T. Pedro A. Del Águila H.

ESTRUCTURA DE LA HOJA:

## PARTE 1: CÓDIGOS (en la parte SUPERIOR de la hoja)
- DNI Alumno: 8 dígitos en cuadros individuales
- Código Aula: texto/números en cuadros (ej: "A101", "B205")  
- DNI Profesor: 8 dígitos en cuadros individuales
- Código Hoja: 9 caracteres alfanuméricos que dice "Hoja: XXXXXXXXX"

## PARTE 2: RESPUESTAS (100 preguntas NUMERADAS del 1 al 100)
Cada pregunta tiene un paréntesis ( ) donde puede haber UNA letra.

REGLAS CRÍTICAS PARA LAS 100 RESPUESTAS:
1. DEBES retornar EXACTAMENTE 100 elementos en el array "respuestas"
2. Recorre pregunta por pregunta del 1 al 100 en ORDEN
3. Para cada pregunta, mira SOLO dentro del paréntesis:
   - Si hay una letra A, B, C, D o E → úsala (en MAYÚSCULA)
   - Si hay letra minúscula a, b, c, d, e → conviértela a MAYÚSCULA
   - Si está VACÍO el paréntesis → usa null
   - Si hay círculo, X, guión, F o cualquier cosa inválida → usa null
4. NO agregues respuestas extras
5. NO omitas preguntas
6. El array debe tener EXACTAMENTE 100 elementos

FORMATO JSON (CRÍTICO - debe ser JSON válido):
{
  "dni_postulante": "12345678",
  "dni_profesor": "87654321",
  "codigo_aula": "A101",
  "codigo_hoja": "A2iDñ5RsW",
  "proceso_admision": "2025-1",
  "respuestas": [
    "A", "B", "C", null, "E", "A", null, "D", ...
  ],
  "confianza_promedio": 0.95,
  "respuestas_detectadas": 98,
  "notas": "Observaciones si las hay"
}

VALIDACIÓN ANTES DE RESPONDER:
- ¿El array "respuestas" tiene EXACTAMENTE 100 elementos? 
- ¿Cada elemento es "A", "B", "C", "D", "E" o null?
- ¿Los DNI tienen 8 dígitos?

RESPONDE SOLO CON EL JSON. NO agregues texto adicional."""

        # Llamada a Claude
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,  # IMPORTANTE: temperatura 0 para máxima consistencia
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
        
        # ====================================================================
        # VALIDACIÓN ESTRICTA
        # ====================================================================
        
        # 1. Verificar campos requeridos
        required_fields = ["dni_postulante", "dni_profesor", "codigo_aula", "respuestas"]
        for field in required_fields:
            if field not in resultado:
                raise ValueError(f"❌ Respuesta de Claude no contiene el campo '{field}'")
        
        # 2. VALIDAR QUE SEAN EXACTAMENTE 100 RESPUESTAS
        if len(resultado["respuestas"]) != 100:
            raise ValueError(
                f"❌ Se esperaban 100 respuestas, se obtuvieron {len(resultado['respuestas'])}. "
                f"Claude no siguió las instrucciones correctamente."
            )
        
        # 3. Validar que cada respuesta sea válida
        respuestas_validadas = []
        for i, resp in enumerate(resultado["respuestas"], 1):
            if resp is None or resp == "" or resp == "null":
                respuestas_validadas.append(None)
            elif isinstance(resp, str):
                resp_upper = resp.strip().upper()
                if resp_upper in ["A", "B", "C", "D", "E"]:
                    respuestas_validadas.append(resp_upper)
                else:
                    # Valor inválido → convertir a null
                    respuestas_validadas.append(None)
                    print(f"⚠️ Pregunta {i}: Valor inválido '{resp}' convertido a null")
            else:
                respuestas_validadas.append(None)
        
        # Reemplazar con respuestas validadas
        resultado["respuestas"] = respuestas_validadas
        
        # 4. Validar DNIs
        if not (isinstance(resultado["dni_postulante"], str) and len(resultado["dni_postulante"]) == 8):
            print(f"⚠️ DNI postulante inválido: {resultado['dni_postulante']}")
        
        if not (isinstance(resultado["dni_profesor"], str) and len(resultado["dni_profesor"]) == 8):
            print(f"⚠️ DNI profesor inválido: {resultado['dni_profesor']}")
        
        # Estadísticas
        respuestas_validas = sum(1 for r in respuestas_validadas if r is not None)
        respuestas_vacias = 100 - respuestas_validas
        
        print(f"✅ Extracción exitosa:")
        print(f"   - Total respuestas: 100")
        print(f"   - Respuestas válidas: {respuestas_validas}")
        print(f"   - Respuestas vacías: {respuestas_vacias}")
        
        return {
            "success": True,
            "datos": resultado,
            "confianza_promedio": resultado.get("confianza_promedio", 0.95),
            "tokens_usados": message.usage.input_tokens + message.usage.output_tokens,
            "estadisticas": {
                "respuestas_validas": respuestas_validas,
                "respuestas_vacias": respuestas_vacias
            }
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Error al parsear JSON de Claude: {str(e)}",
            "respuesta_cruda": respuesta_texto if 'respuesta_texto' in locals() else None
        }
    except ValueError as e:
        # Error de validación
        return {
            "success": False,
            "error": str(e),
            "respuesta_cruda": respuesta_texto if 'respuesta_texto' in locals() else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error inesperado: {str(e)}"
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