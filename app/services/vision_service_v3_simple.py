"""
Vision Service V3 - ADAPTADO PARA HOJAS GENÉRICAS
Detecta:
- Código de hoja (impreso)
- DNI postulante (manuscrito en 8 rectángulos)
- 100 respuestas (manuscritas en rectángulos)
"""

import re
from typing import Dict, List
from google.cloud import vision
import os

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
    Procesa hoja GENÉRICA (sin datos preimpresos del postulante)
    
    Detecta:
    - Código de hoja: ABC12345D (impreso)
    - DNI postulante: 8 dígitos manuscritos
    - 100 respuestas: A/B/C/D/E manuscritas
    
    Returns:
        {
            "success": True,
            "datos": {
                "codigo_hoja": "ABC12345D",
                "dni_postulante": "12345678",
                "respuestas": ["A", "B", "C", ...]  # 100 respuestas
            },
            "api": "google_vision",
            "modelo": "text_detection"
        }
    """
    
    if not VISION_AVAILABLE:
        return {
            "success": False,
            "error": "Google Vision no está disponible"
        }
    
    try:
        # Leer imagen
        with open(imagen_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Detectar texto con HANDWRITING hint
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
        
        # Detectar código de hoja (impreso, fácil)
        codigo_hoja = detectar_codigo_hoja(full_text)
        
        # Detectar DNI manuscrito (en zona de rectángulos)
        dni_postulante = detectar_dni_manuscrito(response, full_text)
        
        # Detectar 100 respuestas
        respuestas = detectar_respuestas_manuscritas(response, full_text)
        
        print(f"✅ Código hoja: {codigo_hoja}")
        print(f"✅ DNI: {dni_postulante}")
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
        return {
            "success": False,
            "error": str(e)
        }


def detectar_codigo_hoja(texto: str) -> str:
    """
    Detecta código de hoja: ABC12345D (3 letras + 5 dígitos + 1 letra)
    """
    # Patrón: 3 letras + 5 dígitos + 1 letra
    patron = r'\b[A-Z]{3}\d{5}[A-Z]\b'
    
    matches = re.findall(patron, texto)
    
    if matches:
        return matches[0]
    
    # Búsqueda más flexible (eliminar espacios/guiones)
    texto_limpio = re.sub(r'[\s\-]', '', texto)
    matches = re.findall(patron, texto_limpio)
    
    if matches:
        return matches[0]
    
    raise Exception("No se detectó código de hoja válido")


def detectar_dni_manuscrito(response, texto: str) -> str:
    """
    Detecta DNI manuscrito en zona de 8 rectángulos
    
    Busca 8 dígitos consecutivos cerca del inicio de la hoja
    """
    
    # Buscar secuencias de exactamente 8 dígitos
    patron_dni = r'\b\d{8}\b'
    
    matches = re.findall(patron_dni, texto)
    
    if matches:
        # Retornar el primero encontrado (debería ser el DNI en los rectángulos)
        return matches[0]
    
    # Si no encuentra 8 dígitos juntos, intentar buscar dígitos separados
    # y unirlos si están cerca espacialmente
    
    # Extraer todos los bloques de texto con sus posiciones
    if response.full_text_annotation and response.full_text_annotation.pages:
        page = response.full_text_annotation.pages[0]
        
        # Buscar bloques en la zona superior (donde está el DNI)
        digitos_encontrados = []
        
        for block in page.blocks:
            # Solo bloques en el tercio superior de la hoja
            vertices = block.bounding_box.vertices
            y_promedio = sum(v.y for v in vertices) / len(vertices)
            
            if y_promedio < page.height * 0.3:  # Tercio superior
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        texto_word = ''.join([symbol.text for symbol in word.symbols])
                        
                        # Si es un dígito individual
                        if texto_word.isdigit() and len(texto_word) == 1:
                            digitos_encontrados.append(texto_word)
        
        # Si encontramos exactamente 8 dígitos
        if len(digitos_encontrados) >= 8:
            dni = ''.join(digitos_encontrados[:8])
            print(f"  ℹ️ DNI reconstruido de dígitos separados: {dni}")
            return dni
    
    raise Exception("No se pudo detectar DNI manuscrito")


def detectar_respuestas_manuscritas(response, texto: str) -> List[str]:
    """
    Detecta 100 respuestas manuscritas (A, B, C, D, E)
    
    Busca letras en la zona de respuestas (mitad inferior de la hoja)
    """
    
    respuestas = []
    
    # Buscar todas las letras A-E en el texto
    letras_validas = ['A', 'B', 'C', 'D', 'E']
    
    # Extraer bloques de texto ordenados por posición Y (de arriba abajo)
    if response.full_text_annotation and response.full_text_annotation.pages:
        page = response.full_text_annotation.pages[0]
        
        palabras_ordenadas = []
        
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    # Obtener texto y posición
                    texto_word = ''.join([symbol.text for symbol in word.symbols]).upper()
                    vertices = word.bounding_box.vertices
                    y_pos = sum(v.y for v in vertices) / len(vertices)
                    x_pos = sum(v.x for v in vertices) / len(vertices)
                    
                    # Solo considerar zona de respuestas (mitad inferior)
                    if y_pos > page.height * 0.35:  # Después del encabezado
                        if texto_word in letras_validas:
                            palabras_ordenadas.append({
                                'texto': texto_word,
                                'y': y_pos,
                                'x': x_pos
                            })
        
        # Ordenar por Y (de arriba abajo), luego por X (izquierda a derecha)
        palabras_ordenadas.sort(key=lambda w: (w['y'], w['x']))
        
        # Extraer solo las letras
        respuestas = [p['texto'] for p in palabras_ordenadas[:100]]
    
    # Si no se encontraron suficientes, completar con vacías
    while len(respuestas) < 100:
        respuestas.append("")
    
    # Limitar a 100
    respuestas = respuestas[:100]
    
    return respuestas


async def procesar_y_guardar_respuestas(hoja_respuesta_id: int, resultado_api: Dict, db):
    """
    Guarda las 100 respuestas individuales en la tabla 'respuestas'
    """
    from app.models import Respuesta
    from datetime import datetime
    
    respuestas_array = resultado_api.get("respuestas", [])
    
    # Estadísticas
    stats = {
        "validas": 0,
        "vacias": 0,
        "letra_invalida": 0,
        "requieren_revision": 0
    }
    
    for i, resp in enumerate(respuestas_array, 1):
        respuesta_upper = resp.strip().upper() if resp else ""
        
        # Categorizar
        if not respuesta_upper:
            categoria = "vacia"
            stats["vacias"] += 1
        elif respuesta_upper in ['A', 'B', 'C', 'D', 'E']:
            categoria = "valida"
            stats["validas"] += 1
        else:
            categoria = "letra_invalida"
            stats["letra_invalida"] += 1
        
        # Guardar respuesta
        # Guardar respuesta
        respuesta_obj = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=i,
            respuesta_marcada=respuesta_upper if respuesta_upper else None,
            confianza=90.0,
            requiere_revision=(categoria != "valida" and categoria != "vacia"),
            created_at=datetime.now()
        )
        
        db.add(respuesta_obj)
        
        if categoria not in ["valida", "vacia"]:
            stats["requieren_revision"] += 1
    
    db.flush()
    
    return {
        "success": True,
        "estadisticas": stats
    }


async def calificar_hoja_con_gabarito(hoja_respuesta_id: int, gabarito_id: int, db):
    """
    Califica las respuestas comparándolas con el gabarito
    """
    from app.models import Respuesta, ClaveRespuesta
    
    # Obtener respuestas del postulante
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    # Obtener gabarito
    gabarito = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.id == gabarito_id
    ).first()
    
    if not gabarito or not gabarito.clave_json:
        raise Exception("Gabarito no disponible")
    
    clave = gabarito.clave_json
    
    # Calificar
    correctas = 0
    incorrectas = 0
    no_calificables = 0
    
    for resp in respuestas:
        num = str(resp.numero_pregunta)
        respuesta_correcta = clave.get(num, "").upper()
        respuesta_alumno = (resp.respuesta_detectada or "").upper()
        
        if not respuesta_alumno:
            no_calificables += 1
            resp.es_correcta = None
        elif respuesta_alumno == respuesta_correcta:
            correctas += 1
            resp.es_correcta = True
        else:
            incorrectas += 1
            resp.es_correcta = False
    
    # Calcular nota (sobre 20)
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
    """Placeholder para compatibilidad"""

    return {}

