"""
REEMPLAZAR en app/services/pdf_generator.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime
import pytz

def generar_hoja_respuestas_pdf(
    output_path: str,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str,
    proceso: str = "2025-2"
):
    """
    Genera PDF con diseño COMPACTO y OPTIMIZADO.
    
    MEJORAS v2:
    - Marco más alto (90% de la altura)
    - Columnas superiores MÁS JUNTAS (más compactas)
    - Respuestas con menos separación horizontal
    - MÁS espacio para firma (40pt)
    - Fecha-hora REAL de impresión
    """
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4  # 595 x 842 puntos
    
    # ========================================================================
    # MARCOS - MÁS ALTOS (90% altura en lugar de 80%)
    # ========================================================================
    
    # Marco GRIS externo
    margen_papel = 15
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.rect(margen_papel, margen_papel, width - 2*margen_papel, height - 2*margen_papel)
    
    # Marco NEGRO grueso - EXTENDIDO VERTICALMENTE
    margen_interno_h = 50  # Reducido de 60 a 50 (más ancho)
    margen_interno_v = 40  # Reducido de 60 a 40 (más alto)
    
    area_x = margen_interno_h
    area_y = margen_interno_v
    area_width = width - 2*margen_interno_h
    area_height = height - 2*margen_interno_v  # 90% de altura aprox
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(area_x, area_y, area_width, area_height)
    
    # ========================================================================
    # MARCAS DE ENCUADRE
    # ========================================================================
    marca_size = 15
    c.setLineWidth(2)
    
    # Superior izquierda
    c.line(area_x, area_y + area_height, area_x + marca_size, area_y + area_height)
    c.line(area_x, area_y + area_height, area_x, area_y + area_height - marca_size)
    
    # Superior derecha
    c.line(area_x + area_width, area_y + area_height, area_x + area_width - marca_size, area_y + area_height)
    c.line(area_x + area_width, area_y + area_height, area_x + area_width, area_y + area_height - marca_size)
    
    # Inferior izquierda
    c.line(area_x, area_y, area_x + marca_size, area_y)
    c.line(area_x, area_y, area_x, area_y + marca_size)
    
    # Inferior derecha
    c.line(area_x + area_width, area_y, area_x + area_width - marca_size, area_y)
    c.line(area_x + area_width, area_y, area_x + area_width, area_y + marca_size)
    
    # ========================================================================
    # CONTENIDO
    # ========================================================================
    
    padding = 12  # Reducido de 15 a 12
    x_start = area_x + padding
    y = area_y + area_height - padding - 15
    content_width = area_width - 2*padding
    
    # ------------------------------------------------------------------------
    # ENCABEZADO
    # ------------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 13)  # Reducido de 14 a 13
    c.drawCentredString(width/2, y, "I. S. T. Pedro A. Del Águila H.")
    y -= 14  # Reducido de 16 a 14
    
    c.setFont("Helvetica", 10)  # Reducido de 11 a 10
    c.drawCentredString(width/2, y, f"EXAMEN DE ADMISIÓN - Proceso {proceso}")
    y -= 16  # Reducido de 20 a 16
    
    c.setLineWidth(1)
    c.line(x_start, y, x_start + content_width, y)
    y -= 12  # Reducido de 15 a 12
    
    # ------------------------------------------------------------------------
    # CÓDIGOS EN 4 COLUMNAS - MÁS COMPACTOS
    # ------------------------------------------------------------------------
    
    # Ancho de columna reducido para que estén más juntas
    col_width = content_width / 5  # Cambio: ahora uso 5 divisiones pero solo 4 columnas
    
    # Posiciones más compactas (empiezan más cerca del inicio)
    col1_x = x_start + col_width * 0.4
    col2_x = x_start + col_width * 1.4
    col3_x = x_start + col_width * 2.6
    col4_x = x_start + col_width * 3.8
    
    # Labels
    c.setFont("Helvetica-Bold", 7)  # Reducido de 8 a 7
    c.drawCentredString(col1_x, y, "DNI-POSTULANTE")
    c.drawCentredString(col2_x, y, "CÓD-AULA")
    c.drawCentredString(col3_x, y, "DNI-PROFESOR")
    c.drawCentredString(col4_x, y, "CÓD-HOJA")
    y -= 12  # Reducido de 14 a 12
    
    # Valores
    c.setFont("Helvetica-Bold", 10)  # Reducido de 11 a 10
    c.drawCentredString(col1_x, y, dni_postulante)
    c.drawCentredString(col2_x, y, codigo_aula)
    c.drawCentredString(col3_x, y, dni_profesor)
    c.drawCentredString(col4_x, y, codigo_hoja)
    y -= 15  # Reducido de 18 a 15
    
    c.setLineWidth(0.5)
    c.line(x_start, y, x_start + content_width, y)
    y -= 10  # Reducido de 12 a 10
    
    # ------------------------------------------------------------------------
    # INSTRUCCIONES
    # ------------------------------------------------------------------------
    c.setFillColor(colors.grey)
    c.setFont("Helvetica", 6.5)  # Reducido de 7 a 6.5
    c.drawString(x_start, y, "Escriba entre los paréntesis la letra de su respuesta, solo en mayúsculas (A, B, C, D, E)")
    y -= 7  # Reducido de 8 a 7
    c.drawString(x_start, y, "Si no sabe la respuesta puede dejar en blanco, pero no use símbolos, ni círculos, ni sombrre los espacios.")
    y -= 12  # Reducido de 15 a 12
    
    c.setFillColor(colors.black)
    
    # ------------------------------------------------------------------------
    # RESPUESTAS: 5 POR FILA × 20 FILAS = 100
    # ------------------------------------------------------------------------
    
    # CRÍTICO: Reservar 40pt para firma (más espacio)
    espacio_disponible = y - (area_y + padding + 40)  # Aumentado de 25 a 40
    filas_totales = 20
    altura_por_fila = espacio_disponible / filas_totales
    
    # Columnas MÁS COMPACTAS (menos espacio horizontal)
    col_ancho = content_width / 5.5  # Cambio: de 5 a 5.5 para hacerlas más juntas
    
    pregunta_num = 1
    
    for fila in range(filas_totales):
        x = x_start
        
        for col in range(5):
            if pregunta_num <= 100:
                # Número
                c.setFont("Helvetica-Bold", 8)  # Reducido de 9 a 8
                c.drawString(x, y, f"{pregunta_num}.")
                
                # Paréntesis
                c.setFont("Helvetica", 9)  # Reducido de 10 a 9
                c.drawString(x + 16, y, "(   )")  # Reducido de 18 a 16
                
                pregunta_num += 1
            
            x += col_ancho
        
        y -= altura_por_fila
    
    # ------------------------------------------------------------------------
    # PIE DE PÁGINA - MÁS ESPACIO + FECHA-HORA REAL
    # ------------------------------------------------------------------------
    y = area_y + padding + 8
    
    c.setFont("Helvetica", 7)  # Reducido de 8 a 7
    c.drawString(x_start, y, "Firma del Profesor")
    c.line(x_start + 70, y - 2, x_start + 190, y - 2)  # Línea más larga
    
    # FECHA-HORA REAL DE IMPRESIÓN
    peru_tz = pytz.timezone('America/Lima')
    fecha_hora_peru = datetime.now(peru_tz).strftime("%d/%m/%Y %H:%M")
    
    fecha_x = x_start + content_width - 110
    c.drawString(fecha_x, y, f"Fecha: {fecha_hora_peru}")
    
    # ------------------------------------------------------------------------
    # GUARDAR
    # ------------------------------------------------------------------------
    c.save()
    
    return {
        "success": True,
        "codigo_hoja": codigo_hoja,
        "filepath": output_path
    }