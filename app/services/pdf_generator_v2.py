"""
Generador de PDFs V2 - OPTIMIZADO para captura con cámaras de baja resolución
Ubicación: app/services/pdf_generator_v2.py

MEJORAS:
- Códigos 18pt (antes 11pt)
- Diseño más compacto y centrado
- Columnas más juntas (1cm separación)
- Márgenes reducidos (1.5cm)
- Marco negro más grueso (3pt)
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
    
    ESPECIFICACIONES:
    - A4: 21 x 29.7 cm (595 x 842 puntos)
    - Márgenes: 1.5cm
    - Marco negro: 3pt (detección OpenCV)
    - Códigos: 18pt (legibles desde lejos)
    - Números: 11pt
    - Columnas: 1cm separación
    - TODO CENTRADO
    """
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # ========================================================================
    # MÁRGENES Y ÁREA ÚTIL
    # ========================================================================
    margen_externo = 1.5 * cm  # 1.5cm según especificación
    
    # Marco GRIS muy fino (borde papel)
    c.setStrokeColor(colors.lightgrey)
    c.setLineWidth(0.3)
    c.rect(margen_externo, margen_externo, 
           width - 2*margen_externo, height - 2*margen_externo)
    
    # Marco NEGRO GRUESO para detección OpenCV (más adentro)
    margen_marco = margen_externo + 0.5*cm
    area_x = margen_marco
    area_y = margen_marco
    area_width = width - 2*margen_marco
    area_height = height - 2*margen_marco
    
    c.setStrokeColor(colors.black)
    c.setLineWidth(3)  # Marco grueso para OpenCV
    c.rect(area_x, area_y, area_width, area_height)
    
    # Marcas L en esquinas (ayuda a OpenCV)
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
    # CONTENIDO (padding interno reducido)
    # ========================================================================
    padding = 0.8 * cm  # Reducido para compactar
    x_start = area_x + padding
    y = area_y + area_height - padding - 0.8*cm
    content_width = area_width - 2*padding
    
    # ------------------------------------------------------------------------
    # ENCABEZADO COMPACTO
    # ------------------------------------------------------------------------
    c.setFont("Helvetica-Bold", 12)  # Reducido de 14
    c.drawCentredString(width/2, y, "I. S. T. Pedro A. Del Águila H.")
    y -= 0.5*cm
    
    c.setFont("Helvetica", 9)  # Reducido de 11
    c.drawCentredString(width/2, y, f"EXAMEN DE ADMISIÓN - Proceso {proceso}")
    y -= 0.7*cm
    
    c.setLineWidth(1.5)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.6*cm
    
    # ------------------------------------------------------------------------
    # CÓDIGOS - 18PT (MÁS GRANDES) Y MÁS JUNTOS
    # ------------------------------------------------------------------------
    
    # Separación entre columnas: 1cm (muy compacto)
    col_width = content_width / 4.5  # Más compacto que antes
    
    col1_x = x_start + col_width * 0.5
    col2_x = x_start + col_width * 1.5
    col3_x = x_start + col_width * 2.5
    col4_x = x_start + col_width * 3.5
    
    # Labels pequeños
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(col1_x, y, "DNI-POSTULANTE")
    c.drawCentredString(col2_x, y, "CÓD-AULA")
    c.drawCentredString(col3_x, y, "DNI-PROFESOR")
    c.drawCentredString(col4_x, y, "CÓD-HOJA")
    y -= 0.5*cm
    
    # Valores GRANDES (18pt según especificación)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(col1_x, y, dni_postulante)
    c.drawCentredString(col2_x, y, codigo_aula)
    c.drawCentredString(col3_x, y, dni_profesor)
    c.drawCentredString(col4_x, y, codigo_hoja)
    y -= 0.7*cm
    
    # Línea gruesa separadora
    c.setLineWidth(2)
    c.line(x_start, y, x_start + content_width, y)
    y -= 0.5*cm
    
    # ------------------------------------------------------------------------
    # INSTRUCCIONES COMPACTAS
    # ------------------------------------------------------------------------
    c.setFillColor(colors.grey)
    c.setFont("Helvetica", 6)
    c.drawString(x_start, y, "Marque con letra MAYÚSCULA (A, B, C, D, E) dentro de los paréntesis.")
    y -= 0.3*cm
    c.drawString(x_start, y, "No use símbolos, ni círculos. Deje en blanco si no sabe la respuesta.")
    y -= 0.5*cm
    
    c.setFillColor(colors.black)
    
    # ------------------------------------------------------------------------
    # RESPUESTAS: 5 COLUMNAS × 20 FILAS = 100
    # COLUMNAS MÁS JUNTAS (1cm separación)
    # ------------------------------------------------------------------------
    
    # Calcular espacio disponible para respuestas
    espacio_pie = 1.2*cm  # Espacio para firma
    espacio_disponible = y - (area_y + padding + espacio_pie)
    
    filas_totales = 20
    altura_por_fila = espacio_disponible / filas_totales  # ~6mm según spec
    
    # Ancho de columna reducido (1cm separación)
    col_ancho = content_width / 5.3  # Más compacto
    
    pregunta_num = 1
    
    for fila in range(filas_totales):
        x = x_start + 0.2*cm  # Pequeño margen izquierdo
        
        for col in range(5):
            if pregunta_num <= 100:
                # Número de pregunta (11pt según spec)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(x, y, f"{pregunta_num}.")
                
                # Paréntesis (11pt)
                c.setFont("Helvetica", 11)
                c.drawString(x + 0.7*cm, y, "(   )")
                
                pregunta_num += 1
            
            x += col_ancho
        
        y -= altura_por_fila
    
    # ------------------------------------------------------------------------
    # PIE DE PÁGINA - MÁS ESPACIO PARA FIRMA
    # ------------------------------------------------------------------------
    y = area_y + padding + 0.4*cm
    
    c.setFont("Helvetica", 7)
    
    # Firma (izquierda)
    c.drawString(x_start, y, "Firma del Profesor:")
    c.line(x_start + 2.5*cm, y - 0.1*cm, x_start + 6*cm, y - 0.1*cm)
    
    # Fecha (derecha) - con hora REAL de Perú
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
        "version": "v2_optimizado"
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
    """
    Alias para compatibilidad con código existente.
    Llama a la versión V2 optimizada.
    """
    return generar_hoja_respuestas_v2(
        output_path, dni_postulante, codigo_aula, 
        dni_profesor, codigo_hoja, proceso
    )