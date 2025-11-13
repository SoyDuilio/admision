"""
Generador de PDFs V2 - CORREGIDO
Ubicación: app/services/pdf_generator_v2.py

CORRECCIONES:
- Código de hoja SEPARADO del DNI profesor (línea aparte)
- Caracteres espaciados para mejor OCR
- Alineado a la derecha
- Instrucciones más grandes (8pt)
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime
import pytz


def generar_hoja_respuestas_v2(
    output_path: str,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str,
    proceso: str = "2025-2"
):
    """
    Genera PDF OPTIMIZADO para lectura con cámaras de baja resolución.
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
    # CÓDIGOS - AHORA CON CÓDIGO DE HOJA SEPARADO
    # ------------------------------------------------------------------------
    
    # LÍNEA 1: DNI Postulante, Código Aula, DNI Profesor (3 columnas)
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
    y -= 0.9*cm  # Más espacio antes del código de hoja
    
    # LÍNEA 2: CÓDIGO DE HOJA (SEPARADO Y ALINEADO A LA DERECHA)
    c.setFont("Helvetica-Bold", 8)
    label_x = x_start + content_width - 4.5*cm
    c.drawString(label_x, y, "CÓDIGO DE HOJA:")
    y -= 0.6*cm
    
    # Código con ESPACIADO MODERADO entre caracteres
    c.setFont("Courier-Bold", 18)  # 18pt en lugar de 20pt
    
    # Espaciado sutil: agregar medio espacio entre caracteres
    codigo_con_espacios = ""
    for i, char in enumerate(codigo_hoja):
        codigo_con_espacios += char
        if i < len(codigo_hoja) - 1:  # No agregar espacio después del último
            codigo_con_espacios += " "  # 1 espacio (no 2)
    
    # Alinear a la derecha
    codigo_width = c.stringWidth(codigo_con_espacios, "Courier-Bold", 18)
    codigo_x = x_start + content_width - codigo_width - 0.3*cm
    c.drawString(codigo_x, y, codigo_con_espacios)
    y -= 0.8*cm
    
    # Línea gruesa separadora
    c.setLineWidth(2)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.6*cm
    
    # ------------------------------------------------------------------------
    # INSTRUCCIONES MÁS GRANDES (8pt en lugar de 6pt)
    # ------------------------------------------------------------------------
    c.setFillColor(colors.grey)
    c.setFont("Helvetica-Bold", 8)  # Más grande y bold
    
    # Primera línea
    texto1 = "Marque con letra MAYÚSCULA (A, B, C, D, E) dentro de los paréntesis."
    c.drawString(x_start, y, texto1)
    y -= 0.35*cm
    
    # Segunda línea
    texto2 = "No use símbolos, ni círculos. Deje en blanco si no sabe la respuesta."
    c.drawString(x_start, y, texto2)
    y -= 0.6*cm
    
    c.setFillColor(colors.black)
    
    # ------------------------------------------------------------------------
    # RESPUESTAS: 5 COLUMNAS × 20 FILAS = 100
    # ------------------------------------------------------------------------
    
    # Calcular espacio disponible
    espacio_pie = 1.2*cm
    espacio_disponible = y - (area_y + padding + espacio_pie)
    
    filas_totales = 20
    altura_por_fila = espacio_disponible / filas_totales
    
    col_ancho = content_width / 5.3
    
    pregunta_num = 1
    
    for fila in range(filas_totales):
        x = x_start + 0.2*cm
        
        for col in range(5):
            if pregunta_num <= 100:
                # Número de pregunta
                c.setFont("Helvetica-Bold", 11)
                c.drawString(x, y, f"{pregunta_num}.")
                
                # Paréntesis
                c.setFont("Helvetica", 11)
                c.drawString(x + 0.7*cm, y, "(   )")
                
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
        "version": "v2_optimizado_corregido"
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
    return generar_hoja_respuestas_v2(
        output_path, dni_postulante, codigo_aula, 
        dni_profesor, codigo_hoja, proceso
    )