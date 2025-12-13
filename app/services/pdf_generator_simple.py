"""
Generador de PDFs GENÉRICOS - Versión Final
100 preguntas | Rectángulos optimizados | Instrucciones claras
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime
import pytz


def generar_hoja_generica(
    output_path: str,
    numero_hoja: int,
    codigo_hoja: str,
    proceso: str,
    descripcion: str = "Examen de Admisión"
):
    """
    Genera hoja de respuestas genérica - 100 preguntas
    """
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # ========================================================================
    # MÁRGENES Y ÁREA ÚTIL
    # ========================================================================
    margen_externo = 1.5 * cm
    
    # Marco GRIS
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.3)
    c.rect(margen_externo, margen_externo, 
           width - 2*margen_externo, height - 2*margen_externo)
    
    # Marco NEGRO GRUESO
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
    y -= 0.55*cm
    
    # ------------------------------------------------------------------------
    # DNI POSTULANTE (8 RECTÁNGULOS MÁS ALTOS)
    # ------------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_start, y, "DNI-POSTULANTE")
    y -= 0.45*cm
    
    # Rectángulos más altos
    rect_ancho = 1.0*cm      # 10mm (antes 9mm)
    rect_alto = 0.85*cm      # 8.5mm (antes 6.5mm) ← +30%
    espaciado = 0.18*cm      # Más espacio entre rectángulos
    
    total_ancho_dni = (8 * rect_ancho) + (7 * espaciado)
    dni_start_x = x_start + (content_width - total_ancho_dni) / 2
    
    c.setLineWidth(1.2)
    c.setStrokeColor(colors.black)
    
    for i in range(8):
        rect_x = dni_start_x + (i * (rect_ancho + espaciado))
        c.rect(rect_x, y - rect_alto, rect_ancho, rect_alto, fill=0)
        
        c.setFont("Helvetica", 6)
        c.setFillColor(colors.grey)
        c.drawCentredString(rect_x + rect_ancho/2, y - rect_alto - 0.25*cm, str(i+1))
        c.setFillColor(colors.black)
    
    y -= rect_alto + 0.45*cm
    
    # ------------------------------------------------------------------------
    # N° ORDEN + CÓDIGO
    # ------------------------------------------------------------------------
    col_orden_x = x_start + content_width * 0.25
    col_codigo_x = x_start + content_width * 0.75
    
    # N° Orden
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(col_orden_x, y, "N° Orden")
    y_circulo = y - 0.55*cm
    
    circulo_radio = 0.45*cm
    c.setLineWidth(2.5)
    c.setStrokeColor(colors.black)
    c.circle(col_orden_x, y_circulo, circulo_radio, fill=0)
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(col_orden_x, y_circulo - 0.22*cm, str(numero_hoja))
    
    # Código de hoja
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(col_codigo_x, y, "CÓDIGO DE HOJA:")
    c.setFont("Courier-Bold", 18)
    c.drawCentredString(col_codigo_x, y - 0.55*cm, codigo_hoja)
    
    y -= 1.15*cm
    
    # Línea separadora
    c.setLineWidth(2)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.55*cm
    
    # ------------------------------------------------------------------------
    # INSTRUCCIONES MEJORADAS
    # ------------------------------------------------------------------------
    c.setFillColor(colors.grey)
    c.setFont("Helvetica-Bold", 8)
    
    texto1 = "Marque con letra MAYÚSCULA (A, B, C, D o E) dentro del recuadro."
    c.drawString(x_start, y, texto1)
    y -= 0.32*cm
    
    texto2 = "Imite las letras impresas: A B C D E    |    Deje en blanco si no sabe."
    c.drawString(x_start, y, texto2)
    y -= 0.55*cm
    
    c.setFillColor(colors.black)
    
    # ------------------------------------------------------------------------
    # RESPUESTAS: 100 PREGUNTAS (5×20) - RECTÁNGULOS MÁS ALTOS
    # ------------------------------------------------------------------------
    espacio_pie = 1.5*cm  # ← Aumentado para dar más espacio a firma
    espacio_disponible = y - (area_y + padding + espacio_pie)
    
    filas_totales = 20
    altura_por_fila = espacio_disponible / filas_totales
    
    col_ancho = content_width / 5.2
    
    # Rectángulos más altos
    rect_ancho_resp = 0.75*cm
    rect_alto_resp = 0.5*cm  # ← Aumentado de 0.45cm
    
    pregunta_num = 1
    
    for fila in range(filas_totales):
        x = x_start + 0.1*cm
        
        for col in range(5):
            if pregunta_num <= 100:
                # Número
                c.setFont("Helvetica-Bold", 9)
                num_y = y + (rect_alto_resp / 2) - 0.12*cm
                c.drawString(x, num_y, f"{pregunta_num}.")
                
                # Rectángulo
                rect_x = x + 0.6*cm
                rect_y = y - 0.05*cm
                
                c.setLineWidth(1)
                c.setStrokeColor(colors.black)
                c.rect(rect_x, rect_y, rect_ancho_resp, rect_alto_resp, fill=0)
                
                pregunta_num += 1
            
            x += col_ancho
        
        y -= altura_por_fila
    
    # ------------------------------------------------------------------------
    # PIE: SECCIÓN PROFESOR CON MÁS ESPACIO
    # ------------------------------------------------------------------------
    y = area_y + padding + 1*cm  # ← Subido para dar más espacio
    
    # Recuadro
    c.setFillColor(colors.HexColor('#f5f5f5'))
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(x_start, y - 0.5*cm, content_width, 1.1*cm, fill=1, stroke=1)
    
    c.setFillColor(colors.black)
    
    # Título
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x_start + 0.2*cm, y + 0.35*cm, "DATOS DEL PROFESOR VIGILANTE")
    
    # Campos ajustados
    campo_y = y - 0.05*cm
    
    c.setFont("Helvetica", 7)
    
    # DNI (más corto)
    c.drawString(x_start + 0.3*cm, campo_y, "DNI:")
    c.setLineWidth(0.5)
    c.line(x_start + 1*cm, campo_y - 0.1*cm, x_start + 3*cm, campo_y - 0.1*cm)  # ← Acortado
    
    # Nombres y Apellidos
    c.drawString(x_start + 3.5*cm, campo_y, "Nombres y Apellidos:")
    c.line(x_start + 6.5*cm, campo_y - 0.1*cm, x_start + 11*cm, campo_y - 0.1*cm)
    
    # Firma (más largo)
    c.drawString(x_start + 11.5*cm, campo_y, "Firma:")
    c.line(x_start + 13*cm, campo_y - 0.1*cm, x_start + content_width - 0.3*cm, campo_y - 0.1*cm)  # ← Extendido
    
    # Footer con más espacio arriba
    y_footer = area_y + padding + 0.3*cm
    peru_tz = pytz.timezone('America/Lima')
    fecha_hora = datetime.now(peru_tz).strftime("%d/%m/%Y %H:%M")
    
    c.setFont("Helvetica", 6)
    c.setFillColor(colors.grey)
    c.drawCentredString(width/2, y_footer, 
                       f"POSTULANDO | Código: {codigo_hoja} | Hoja N° {numero_hoja} | {fecha_hora}")
    
    # ------------------------------------------------------------------------
    # GUARDAR
    # ------------------------------------------------------------------------
    c.save()
    
    print(f"  ✅ PDF generado: hoja_{numero_hoja:03d}_{codigo_hoja}.pdf")