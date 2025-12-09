"""
Vision Service V3 - SIMPLE con detección precisa de DNI
"""

import re
from typing import Dict, List
from datetime import datetime

# Inicializar cliente Google Vision
try:
    from app.services.google_vision import google_vision_service
    
    if google_vision_service.is_available():
        vision_client = google_vision_service.client
        VISION_AVAILABLE = True
    else:
        print(f"⚠️ Google Vision no disponible")
        VISION_AVAILABLE = False
        vision_client = None
        
except Exception as e:
    print(f"⚠️ Google Vision no disponible: {str(e)}")
    VISION_AVAILABLE = False
    vision_client = None


async def procesar_hoja_completa_v3(imagen_path: str) -> Dict:
    """
    Procesa hoja genérica: código + DNI manuscrito + 100 respuestas
    """
    
    if not VISION_AVAILABLE:
        return {
            "success": False,
            "error": "Google Vision no está disponible"
        }
    
    try:
        from google.cloud import vision
        
        # Leer imagen
        with open(imagen_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Detectar texto
        image_context = vision.ImageContext(
            language_hints=['es', 'en']
        )
        
        response = vision_client.document_text_detection(
            image=image,
            image_context=image_context
        )
        
        if response.error.message:
            raise Exception(f"Error API: {response.error.message}")
        
        # Extraer texto completo
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        
        print(f"\n📄 Texto detectado ({len(full_text)} caracteres)")
        
        # Detectar código de hoja (impreso)
        codigo_hoja = detectar_codigo_hoja(full_text)
        
        # Detectar DNI manuscrito (MEJORADO - coordenadas precisas)
        dni_postulante = detectar_dni_manuscrito_preciso(response)
        
        # Detectar 100 respuestas
        respuestas = detectar_respuestas_manuscritas(response)
        
        print(f"✅ Código hoja: {codigo_hoja}")
        print(f"✅ DNI: {dni_postulante if dni_postulante else '(no detectado)'}")
        print(f"✅ Respuestas: {len(respuestas)}/100")
        
        return {
            "success": True,
            "datos": {
                "codigo_hoja": codigo_hoja,
                "dni_postulante": dni_postulante,
                "respuestas": respuestas
            },
            "api": "google_vision",
            "modelo": "document_text_detection",
            "apis_usadas": ["google_vision:document_text_detection"]
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def detectar_codigo_hoja(texto: str) -> str:
    """Detecta código: ABC12345D"""
    patron = r'\b[A-Z]{3}\d{5}[A-Z]\b'
    matches = re.findall(patron, texto)
    
    if matches:
        return matches[0]
    
    texto_limpio = re.sub(r'[\s\-]', '', texto)
    matches = re.findall(patron, texto_limpio)
    
    if matches:
        return matches[0]
    
    raise Exception("No se detectó código de hoja válido")


def detectar_dni_manuscrito_preciso(response) -> str:
    """
    DETECCIÓN PRECISA DE DNI EN ZONA DE 8 RECTÁNGULOS
    
    Basado en pdf_generator_simple.py:
    - Rectángulos: 8 × 0.9cm con espaciado 0.15cm
    - Total ancho: 8.25 cm (centrados)
    - Ubicación: ~3.5-4.5 cm desde arriba
    - Altura rectángulos: 0.65 cm
    """
    
    print(f"\n🔍 Buscando DNI en zona precisa...")
    
    if not response.full_text_annotation or not response.full_text_annotation.pages:
        print(f"  ⚠️ No hay datos de páginas")
        return ""
    
    page = response.full_text_annotation.pages[0]
    page_width = page.width
    page_height = page.height
    
    print(f"  📏 Dimensiones página: {page_width}px × {page_height}px")
    
    # ========================================================================
    # COORDENADAS PRECISAS BASADAS EN PDF
    # ========================================================================
    
    # A4 en puntos: 595.28 × 841.89
    # Márgenes: 1.5cm ext + 0.5cm marco = 2cm = ~56.7 puntos
    # Rectángulos DNI centrados, 8.25cm de ancho total
    # Posición Y: ~3.5-4.5cm desde arriba = ~99-127 puntos desde arriba
    #            = ~715-742 puntos desde abajo
    
    dni_zone = {
        'x_min': page_width * 0.25,   # 25% desde izquierda (más centrado)
        'x_max': page_width * 0.75,   # 75% desde izquierda (más centrado)
        'y_min': page_height * 0.84,  # 84% desde abajo (zona DNI)
        'y_max': page_height * 0.91   # 91% desde abajo
    }
    
    print(f"  📍 Zona búsqueda:")
    print(f"     X: {dni_zone['x_min']:.0f} - {dni_zone['x_max']:.0f} px")
    print(f"     Y: {dni_zone['y_min']:.0f} - {dni_zone['y_max']:.0f} px")
    
    digitos_encontrados = []
    
    # Buscar SOLO dígitos en esa zona
    for block in page.blocks:
        for paragraph in block.paragraphs:
            for word in paragraph.words:
                vertices = word.bounding_box.vertices
                x = sum(v.x for v in vertices) / 4
                y = sum(v.y for v in vertices) / 4
                
                # ¿Está dentro de la zona DNI?
                if (dni_zone['x_min'] <= x <= dni_zone['x_max'] and 
                    dni_zone['y_min'] <= y <= dni_zone['y_max']):
                    
                    texto_word = ''.join([s.text for s in word.symbols])
                    
                    # Agregar TODOS los dígitos con su posición X
                    for char in texto_word:
                        if char.isdigit():
                            digitos_encontrados.append((x, char))
                            print(f"     ✓ Dígito '{char}' en X={x:.0f}, Y={y:.0f}")
    
    if not digitos_encontrados:
        print(f"  ⚠️ No se encontraron dígitos en zona DNI")
        return ""
    
    # Ordenar por posición X (izquierda a derecha)
    digitos_encontrados.sort(key=lambda d: d[0])
    
    # Tomar solo los primeros 8
    dni_digitos = [d[1] for d in digitos_encontrados[:8]]
    dni = ''.join(dni_digitos)
    
    if len(dni) == 8:
        print(f"  ✅ DNI detectado: {dni}")
        print(f"     Total dígitos en zona: {len(digitos_encontrados)}")
        return dni
    else:
        print(f"  ⚠️ DNI incompleto: {dni} ({len(dni)}/8 dígitos)")
        return ""


def detectar_respuestas_manuscritas(response) -> List[str]:
    """Detecta 100 respuestas manuscritas (A-E)"""
    
    respuestas = []
    letras_validas = ['A', 'B', 'C', 'D', 'E']
    
    if response.full_text_annotation and response.full_text_annotation.pages:
        page = response.full_text_annotation.pages[0]
        
        palabras_ordenadas = []
        
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    texto_word = ''.join([symbol.text for symbol in word.symbols]).upper()
                    vertices = word.bounding_box.vertices
                    y_pos = sum(v.y for v in vertices) / len(vertices)
                    x_pos = sum(v.x for v in vertices) / len(vertices)
                    
                    # Solo zona de respuestas (debajo del 35% superior)
                    if y_pos < page.height * 0.65:  # 65% desde abajo = 35% desde arriba
                        if texto_word in letras_validas:
                            palabras_ordenadas.append({
                                'texto': texto_word,
                                'y': y_pos,
                                'x': x_pos
                            })
        
        # Ordenar: primero por Y descendente (arriba a abajo), luego por X
        palabras_ordenadas.sort(key=lambda w: (-w['y'], w['x']))
        respuestas = [p['texto'] for p in palabras_ordenadas[:100]]
    
    while len(respuestas) < 100:
        respuestas.append("")
    
    return respuestas[:100]


async def procesar_y_guardar_respuestas(hoja_respuesta_id: int, resultado_api: Dict, db):
    """Guarda las 100 respuestas"""
    from app.models import Respuesta
    
    respuestas_array = resultado_api.get("respuestas", [])
    
    stats = {
        "validas": 0,
        "vacias": 0,
        "letra_invalida": 0,
        "requieren_revision": 0
    }
    
    for i, resp in enumerate(respuestas_array, 1):
        respuesta_upper = resp.strip().upper() if resp else ""
        
        if not respuesta_upper:
            stats["vacias"] += 1
        elif respuesta_upper in ['A', 'B', 'C', 'D', 'E']:
            stats["validas"] += 1
        else:
            stats["letra_invalida"] += 1
        
        respuesta_obj = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=i,
            respuesta_marcada=respuesta_upper if respuesta_upper else None,
            confianza=0.90,
            requiere_revision=(respuesta_upper not in ['A', 'B', 'C', 'D', 'E', '']),
            created_at=datetime.now()
        )
        
        db.add(respuesta_obj)
        
        if respuesta_upper and respuesta_upper not in ['A', 'B', 'C', 'D', 'E']:
            stats["requieren_revision"] += 1
    
    db.flush()
    
    return {
        "success": True,
        "estadisticas": stats
    }


async def calificar_hoja_con_gabarito(hoja_respuesta_id: int, gabarito_id: int, db):
    """Califica con gabarito"""
    from app.models import Respuesta, ClaveRespuesta
    from sqlalchemy import text
    
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.id == gabarito_id
    ).first()
    
    if not gabarito:
        raise Exception("Gabarito no disponible")
    
    # Obtener todas las claves del proceso
    query = text("""
        SELECT numero_pregunta, respuesta_correcta
        FROM clave_respuestas
        WHERE proceso_admision = :proceso
        ORDER BY numero_pregunta
    """)
    
    claves = db.execute(query, {"proceso": gabarito.proceso_admision}).fetchall()
    clave_dict = {str(c.numero_pregunta): c.respuesta_correcta.upper() for c in claves}
    
    correctas = 0
    incorrectas = 0
    no_calificables = 0
    
    for resp in respuestas:
        num = str(resp.numero_pregunta)
        respuesta_correcta = clave_dict.get(num, "").upper()
        respuesta_alumno = (resp.respuesta_marcada or "").upper()
        
        if not respuesta_alumno:
            no_calificables += 1
            resp.es_correcta = None
        elif respuesta_alumno == respuesta_correcta:
            correctas += 1
            resp.es_correcta = True
        else:
            incorrectas += 1
            resp.es_correcta = False
    
    nota_final = (correctas / 100) * 20
    porcentaje = (correctas / 100) * 100
    
    db.flush()
    
    return {
        "correctas": correctas,
        "incorrectas": incorrectas,
        "no_calificables": no_calificables,
        "nota_final": round(nota_final, 2),
        "porcentaje": round(porcentaje, 2)
    }


async def generar_reporte_detallado(*args, **kwargs):
    """Placeholder"""
    return {}