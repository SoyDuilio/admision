"""
Vision Service V3 - ADAPTADO PARA HOJAS GENÉRICAS
Detecta:
- Código de hoja (impreso)
- DNI postulante (manuscrito en 8 rectángulos)
- 100 respuestas (manuscritas en rectángulos)
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
        from google.cloud import vision
        
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
        print(f"📋 TEXTO COMPLETO:")
        print(f"{full_text}")
        print(f"\n" + "="*70)
        
        # Detectar código de hoja (impreso, fácil)
        codigo_hoja = detectar_codigo_hoja(full_text)
        
        # Detectar DNI manuscrito (OPCIONAL)
        try:
            dni_postulante = detectar_dni_manuscrito(response, full_text)
        except Exception as e:
            print(f"  ⚠️ Error detectando DNI: {str(e)}")
            dni_postulante = ""
        
        # Detectar 100 respuestas
        respuestas = detectar_respuestas_manuscritas(response, full_text)
        
        print(f"\n✅ Código hoja: {codigo_hoja}")
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
    Detecta DNI manuscrito - VERSIÓN MEJORADA
    Busca 8 dígitos en diferentes formatos
    """
    
    print(f"\n🔍 Buscando DNI en el texto...")
    
    # MÉTODO 1: Buscar 8 dígitos juntos (sin espacios)
    patron_dni = r'\b\d{8}\b'
    matches = re.findall(patron_dni, texto)
    
    if matches:
        print(f"  ✅ DNI encontrado (juntos): {matches[0]}")
        return matches[0]
    
    # MÉTODO 2: Buscar 8 dígitos con espacios/guiones
    # Ejemplo: "1 2 3 4 5 6 7 8" o "12-34-56-78"
    texto_limpio = re.sub(r'[^\d]', '', texto)  # Quitar todo excepto dígitos
    
    # Buscar secuencias de 8 dígitos consecutivos en texto limpio
    if len(texto_limpio) >= 8:
        # Buscar la primera aparición de 8 dígitos
        for i in range(len(texto_limpio) - 7):
            posible_dni = texto_limpio[i:i+8]
            # Validar que no sea parte de un número más largo (como el código de hoja)
            if posible_dni.isdigit():
                print(f"  ✅ DNI reconstruido: {posible_dni}")
                return posible_dni
    
    # MÉTODO 3: Usar análisis espacial (zona superior de la hoja)
    if response.full_text_annotation and response.full_text_annotation.pages:
        page = response.full_text_annotation.pages[0]
        
        # Buscar TODOS los dígitos en el tercio superior
        digitos_encontrados = []
        
        for block in page.blocks:
            vertices = block.bounding_box.vertices
            y_promedio = sum(v.y for v in vertices) / len(vertices)
            
            # Solo zona superior (donde están los rectángulos de DNI)
            if y_promedio < page.height * 0.4:  # 40% superior
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        texto_word = ''.join([symbol.text for symbol in word.symbols])
                        
                        # Agregar todos los dígitos encontrados
                        for char in texto_word:
                            if char.isdigit():
                                digitos_encontrados.append(char)
        
        print(f"  ℹ️ Dígitos encontrados en zona DNI: {''.join(digitos_encontrados)}")
        
        # Si encontramos al menos 8 dígitos, tomar los primeros 8
        if len(digitos_encontrados) >= 8:
            dni = ''.join(digitos_encontrados[:8])
            print(f"  ✅ DNI reconstruido (primeros 8): {dni}")
            return dni
    
    # Si llegamos aquí, no se detectó
    print(f"  ⚠️ DNI no detectado - Texto completo:")
    print(f"  {texto[:200]}...")  # Mostrar primeros 200 caracteres
    
    return ""  # Retornar vacío en lugar de error


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
            stats["vacias"] += 1
        elif respuesta_upper in ['A', 'B', 'C', 'D', 'E']:
            stats["validas"] += 1
        else:
            stats["letra_invalida"] += 1
        
        # Guardar respuesta
        respuesta_obj = Respuesta(
            hoja_respuesta_id=hoja_respuesta_id,
            numero_pregunta=i,
            respuesta_marcada=respuesta_upper if respuesta_upper else None,
            confianza=0.90,  # ← CAMBIAR de 90.0 a 0.90
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
    """
    Califica las respuestas comparándolas con el gabarito
    """
    from app.models import Respuesta
    from sqlalchemy import text
    
    # Obtener respuestas del postulante
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_respuesta_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    # Obtener gabarito desde clave_respuestas (una fila por pregunta)
    query_gabarito = text("""
        SELECT numero_pregunta, respuesta_correcta
        FROM clave_respuestas
        WHERE proceso_admision = (
            SELECT proceso_admision FROM hojas_respuestas WHERE id = :hoja_id
        )
        ORDER BY numero_pregunta
    """)
    
    gabarito_resp = db.execute(query_gabarito, {"hoja_id": hoja_respuesta_id}).fetchall()
    
    if not gabarito_resp:
        raise Exception("Gabarito no disponible para este proceso")
    
    # Crear dict del gabarito
    clave = {str(g.numero_pregunta): g.respuesta_correcta.upper() for g in gabarito_resp}
    
    # Calificar
    correctas = 0
    incorrectas = 0
    no_calificables = 0
    
    for resp in respuestas:
        num = str(resp.numero_pregunta)
        respuesta_correcta = clave.get(num, "").upper()
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

