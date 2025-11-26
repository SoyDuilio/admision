"""
Endpoint para Generar Documento Oficial de Gabarito - OPTIMIZADO PARA 1 PÁGINA A4
Reemplazar: app/api/documento_oficial_gabarito.py

Genera un PDF A4 vertical con TODO en UNA sola página:
- Logo institucional (espacio reservado)
- 100 respuestas agrupadas por alternativa
- 3 espacios para firmas compactos
- Fecha y código de verificación
- NO se guarda en BD
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from datetime import datetime
import hashlib

router = APIRouter()


@router.post("/generar-documento-oficial-gabarito")
async def generar_documento_oficial_gabarito(data: dict):
    """
    Genera el documento oficial de gabarito para imprimir, firmar y lacrar.
    
    Body:
    {
        "proceso_admision": "2025-2",
        "gabarito": {
            "1": "A", "2": "B", "3": "C", ..., "100": "E"
        },
        "totales": {
            "A": 20, "B": 18, "C": 22, "D": 25, "E": 15
        }
    }
    """
    
    try:
        proceso = data.get('proceso_admision', '2025-2')
        gabarito = data.get('gabarito', {})
        totales = data.get('totales', {})
        
        print(f"\n{'='*70}")
        print(f"📄 GENERANDO DOCUMENTO OFICIAL DE GABARITO")
        print(f"{'='*70}")
        print(f"Proceso: {proceso}")
        print(f"Total preguntas: {len(gabarito)}")
        print(f"Totales por alternativa: {totales}")
        
        # Validaciones
        if len(gabarito) != 100:
            raise HTTPException(status_code=400, detail=f"Debe tener 100 preguntas. Recibido: {len(gabarito)}")
        
        numeros_esperados = set(str(i) for i in range(1, 101))
        numeros_recibidos = set(gabarito.keys())
        if numeros_esperados != numeros_recibidos:
            faltantes = numeros_esperados - numeros_recibidos
            raise HTTPException(status_code=400, detail=f"Faltan las preguntas: {sorted(faltantes)}")
        
        respuestas_validas = {'A', 'B', 'C', 'D', 'E'}
        for num, resp in gabarito.items():
            if resp not in respuestas_validas:
                raise HTTPException(status_code=400, detail=f"Respuesta inválida en pregunta {num}: '{resp}'")
        
        # Generar PDF con márgenes reducidos
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilos compactos
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=8,
            alignment=TA_CENTER
        )
        
        # Logo (espacio reservado - 2x2cm)
        # TODO: Descomentar y ajustar ruta cuando tengas el logo
        # from reportlab.platypus import Image
        # logo = Image('app/static/images/logo.png', width=2*cm, height=2*cm)
        # elements.append(logo)
        
        elements.append(Spacer(1, 0.3*cm))
        
        # Título
        elements.append(Paragraph("DOCUMENTO OFICIAL DE RESPUESTAS CORRECTAS", title_style))
        elements.append(Paragraph(f"GABARITO DEL EXAMEN DE ADMISIÓN {proceso}", subtitle_style))
        
        # Información de generación
        fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        codigo_verificacion = hashlib.sha256(f"{proceso}{fecha_hora}{str(gabarito)}".encode()).hexdigest()[:12].upper()
        
        elements.append(Paragraph(f"Fecha: {fecha_hora} | Código: {codigo_verificacion}", info_style))
        elements.append(Spacer(1, 0.3*cm))
        
        # Resumen de alternativas (tabla pequeña)
        resumen_data = [
            ['Alt', 'Cant'],
            ['A', str(totales.get('A', 0))],
            ['B', str(totales.get('B', 0))],
            ['C', str(totales.get('C', 0))],
            ['D', str(totales.get('D', 0))],
            ['E', str(totales.get('E', 0))],
            ['TOTAL', '100']
        ]
        
        resumen_table = Table(resumen_data, colWidths=[1.5*cm, 1.5*cm])
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dbeafe')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        
        elements.append(resumen_table)
        elements.append(Spacer(1, 0.3*cm))
        
        # Gabarito por alternativas (formato compacto)
        preguntas_por_alternativa = {'A': [], 'B': [], 'C': [], 'D': [], 'E': []}
        
        for num in range(1, 101):
            resp = gabarito.get(str(num), '')
            if resp in preguntas_por_alternativa:
                preguntas_por_alternativa[resp].append(num)
        
        gabarito_data = [['Alt', 'Preguntas respondidas con la alternativa']]
        
        for letra in ['A', 'B', 'C', 'D', 'E']:
            numeros = preguntas_por_alternativa[letra]
            
            # Formatear en grupos de 15 números por línea
            lineas = []
            for i in range(0, len(numeros), 15):
                grupo = numeros[i:i+15]
                lineas.append('  '.join(f"{n:>3}" for n in grupo))
            
            numeros_texto = '\n'.join(lineas)
            
            gabarito_data.append([
                Paragraph(f"<b>{letra}</b>", ParagraphStyle(
                    'Alt',
                    parent=styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor('#1e40af'),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )),
                Paragraph(f"<font name='Courier' size='8'>{numeros_texto}</font>", styles['Normal'])
            ])
        
        gabarito_table = Table(gabarito_data, colWidths=[1.5*cm, 15.5*cm])
        gabarito_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#f1f5f9')),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1e40af')),
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#eff6ff')),
            ('BACKGROUND', (1, 3), (1, 3), colors.HexColor('#eff6ff')),
            ('BACKGROUND', (1, 5), (1, 5), colors.HexColor('#eff6ff')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        elements.append(gabarito_table)
        elements.append(Spacer(1, 0.4*cm))
        
        # Firmas compactas
        firma_style = ParagraphStyle(
            'Firma',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        firmas_data = [[
            Paragraph("__________________<br/><b>DOCENTE ELABORADOR</b><br/><font size='6'>Nombre: _______________</font><br/><font size='6'>DNI: _______________</font>", firma_style),
            Paragraph("__________________<br/><b>COORD. ACADÉMICO</b><br/><font size='6'>Nombre: _______________</font><br/><font size='6'>DNI: _______________</font>", firma_style),
            Paragraph("__________________<br/><b>DIRECTOR/RECTOR</b><br/><font size='6'>Nombre: _______________</font><br/><font size='6'>DNI: _______________</font>", firma_style)
        ]]
        
        firmas_table = Table(firmas_data, colWidths=[5.6*cm, 5.6*cm, 5.6*cm])
        firmas_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER')
        ]))
        
        elements.append(firmas_table)
        elements.append(Spacer(1, 0.2*cm))
        
        # Nota final
        nota_style = ParagraphStyle(
            'Nota',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#ef4444'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph(
            "⚠️ IMPORTANTE: Este documento debe ser firmado, lacrado y resguardado hasta el día del examen.",
            nota_style
        ))
        
        # Construir PDF
        doc.build(elements)
        buffer.seek(0)
        
        filename = f"gabarito_oficial_{proceso}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        print(f"✅ PDF generado: {filename}")
        print(f"   Código: {codigo_verificacion}\n")
        
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))