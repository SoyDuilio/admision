"""
Generador de PDFs V3 - CON RECTÁNGULOS
Ubicación: app/services/pdf_generator_v3.py

MEJORAS V3:
- RECTÁNGULOS en lugar de paréntesis (0.9cm × 0.55cm)
- Código de hoja SIN espacios
- Instrucciones permiten mayúsculas y minúsculas
- Todo alineado dentro de límites consistentes
- Tamaño de letra manuscrita optimizado (hasta 16pt)
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime
import pytz


def generar_hoja_respuestas_v3(
    output_path: str,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str,
    proceso: str = "2025-2"
):
    """
    Genera PDF OPTIMIZADO V3 con rectángulos para mejor detección OCR.
    """
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # ========================================================================
    # MÁRGENES Y ÁREA ÚTIL
    # ========================================================================
    margen_externo = 1.5 * cm
    
    # Marco GRIS muy fino (borde papel)
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.3)
    c.rect(margen_externo, margen_externo, 
           width - 2*margen_externo, height - 2*margen_externo)
    
    # Marco NEGRO GRUESO para detección OpenCV
    margen_marco = margen_externo + 0.5*cm
    area_x = margen_marco
    area_y = margen_marco
    area_width = width - 2*margen_marco
    area_height = height - 2*margen_marco
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(3)
    c.rect(area_x, area_y, area_width, area_height)
    
    # Marcas L en esquinas
    marca_size = 0.8 * cm
    c.setLineWidth(3)
    
    # Superior izquierda
    c.line(area_x, area_y + area_height, area_x + marca_size, area_y + area_height)
    c.line(area_x, area_y + area_height, area_x, area_y + area_height - marca_size)
    
    # Superior derecha
    c.line(area_x + area_width, area_y + area_height, 
           area_x + area_width - marca_size, area_y + area_height)
    c.line(area_x + area_width, area_y + area_height, 
           area_x + area_width, area_y + area_height - marca_size)
    
    # Inferior izquierda
    c.line(area_x, area_y, area_x + marca_size, area_y)
    c.line(area_x, area_y, area_x, area_y + marca_size)
    
    # Inferior derecha
    c.line(area_x + area_width, area_y, area_x + area_width - marca_size, area_y)
    c.line(area_x + area_width, area_y, area_x + area_width, area_y + marca_size)
    
    # ========================================================================
    # CONTENIDO
    # ========================================================================
    padding = 0.8 * cm
    x_start = area_x + padding
    y = area_y + area_height - padding - 0.8*cm
    content_width = area_width - 2*padding
    
    # ------------------------------------------------------------------------
    # ENCABEZADO
    # ------------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width/2, y, "I. S. T. Pedro A. Del Águila H.")
    y -= 0.5*cm
    
    c.setFont("Helvetica", 9)
    c.drawCentredString(width/2, y, f"EXAMEN DE ADMISIÓN - Proceso {proceso}")
    y -= 0.7*cm
    
    c.setLineWidth(1.5)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.6*cm
    
    # ------------------------------------------------------------------------
    # CÓDIGOS - LÍNEA 1: DNI, Aula, DNI Profesor
    # ------------------------------------------------------------------------
    col_width = content_width / 3
    
    col1_x = x_start + col_width * 0.5
    col2_x = x_start + col_width * 1.5
    col3_x = x_start + col_width * 2.5
    
    # Labels
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(col1_x, y, "DNI-POSTULANTE")
    c.drawCentredString(col2_x, y, "CÓD-AULA")
    c.drawCentredString(col3_x, y, "DNI-PROFESOR")
    y -= 0.5*cm
    
    # Valores
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(col1_x, y, dni_postulante)
    c.drawCentredString(col2_x, y, codigo_aula)
    c.drawCentredString(col3_x, y, dni_profesor)
    y -= 0.9*cm
    
    # ------------------------------------------------------------------------
    # LÍNEA 2: CÓDIGO DE HOJA (SIN ESPACIOS, CENTRADO)
    # ------------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(width/2, y, "CÓDIGO DE HOJA:")
    y -= 0.6*cm
    
    # Código SIN espacios
    c.setFont("Courier-Bold", 20)
    c.drawCentredString(width/2, y, codigo_hoja)  # Sin espacios: "UXJ545X"
    y -= 0.8*cm
    
    # Línea gruesa separadora
    c.setLineWidth(2)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.6*cm
    
    # ------------------------------------------------------------------------
    # INSTRUCCIONES MEJORADAS
    # ------------------------------------------------------------------------
    c.setFillColor(colors.grey)
    c.setFont("Helvetica-Bold", 8)
    
    texto1 = "Marque con letra A, B, C, D o E (mayúscula o minúscula) dentro del recuadro."
    c.drawString(x_start, y, texto1)
    y -= 0.35*cm
    
    texto2 = "Use letra clara y grande. Deje en blanco si no sabe la respuesta."
    c.drawString(x_start, y, texto2)
    y -= 0.6*cm
    
    c.setFillColor(colors.black)
    
    # ------------------------------------------------------------------------
    # RESPUESTAS: 5 COLUMNAS × 20 FILAS = 100 CON RECTÁNGULOS
    # ------------------------------------------------------------------------
    
    # Calcular espacio disponible
    espacio_pie = 1.2*cm
    espacio_disponible = y - (area_y + padding + espacio_pie)
    
    filas_totales = 20
    altura_por_fila = espacio_disponible / filas_totales
    
    # Ancho de cada columna
    col_ancho = content_width / 5.2
    
    # Dimensiones del rectángulo
    rect_ancho = 0.9*cm  # ~35px
    rect_alto = 0.55*cm  # ~22px
    
    pregunta_num = 1
    
    for fila in range(filas_totales):
        x = x_start + 0.1*cm
        
        for col in range(5):
            if pregunta_num <= 100:
                # Número de pregunta
                c.setFont("Helvetica-Bold", 11)
                num_y = y + (rect_alto / 2) - 0.15*cm  # Centrado vertical
                c.drawString(x, num_y, f"{pregunta_num}.")
                
                # RECTÁNGULO en lugar de paréntesis
                rect_x = x + 0.7*cm
                rect_y = y - 0.05*cm
                
                c.setLineWidth(1.2)
                c.setStrokeColor(colors.black)
                c.rect(rect_x, rect_y, rect_ancho, rect_alto, fill=0)
                
                # Letra de ejemplo MUY tenue (opcional)
                # c.setFillColorRGB(0.95, 0.95, 0.95)
                # c.setFont("Helvetica", 14)
                # c.drawString(rect_x + 0.25*cm, rect_y + 0.12*cm, "A")
                # c.setFillColor(colors.black)
                
                pregunta_num += 1
            
            x += col_ancho
        
        y -= altura_por_fila
    
    # ------------------------------------------------------------------------
    # PIE DE PÁGINA
    # ------------------------------------------------------------------------
    y = area_y + padding + 0.4*cm
    
    c.setFont("Helvetica", 7)
    
    # Firma (izquierda)
    c.drawString(x_start, y, "Firma del Profesor:")
    c.line(x_start + 2.5*cm, y - 0.1*cm, x_start + 6*cm, y - 0.1*cm)
    
    # Fecha (derecha)
    peru_tz = pytz.timezone('America/Lima')
    fecha_hora = datetime.now(peru_tz).strftime("%d/%m/%Y %H:%M")
    
    fecha_x = x_start + content_width - 4*cm
    c.drawString(fecha_x, y, f"Fecha: {fecha_hora}")
    
    # ------------------------------------------------------------------------
    # GUARDAR
    # ------------------------------------------------------------------------
    c.save()
    
    return {
        "success": True,
        "codigo_hoja": codigo_hoja,
        "filepath": output_path,
        "version": "v3_rectangulos"
    }


# ============================================================================
# FUNCIÓN DE COMPATIBILIDAD
# ============================================================================

def generar_hoja_respuestas_pdf(
    output_path: str,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str,
    proceso: str = "2025-2"
):
    """Alias para compatibilidad con código existente."""
    return generar_hoja_respuestas_v3(
        output_path, dni_postulante, codigo_aula, 
        dni_profesor, codigo_hoja, proceso
    )