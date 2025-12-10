"""
Vision Service V3 - SIMPLE usando Gemini 2.5 Flash
Usa schema estructurado para extracción precisa
"""

import os
from typing import Dict
from app.services.gemini_extractor_structured import extract_data_compatible


async def procesar_hoja_completa_v3(imagen_path: str) -> Dict:
    """
    Procesa hoja usando Gemini 2.5 Flash con schema estructurado
    
    IMPORTANTE: Esta versión usa Gemini, NO Google Vision OCR
    
    Returns:
        {
            "success": True,
            "datos": {
                "codigo_hoja": "ABC12345D",
                "dni_postulante": "12345678",
                "respuestas": ["A", "B", None, ...]  # 100 elementos
            },
            "api": "gemini-structured",
            "modelo": "gemini-2.5-flash"
        }
    """
    
    try:
        print(f"\n{'='*70}")
        print(f"🚀 PROCESANDO CON GEMINI 2.5 FLASH")
        print(f"{'='*70}")
        
        # Llamar al extractor de Gemini
        resultado = await extract_data_compatible(imagen_path)
        
        if not resultado["success"]:
            return resultado
        
        # Extraer datos
        datos = resultado["data"]
        
        # Validar que tenga 100 respuestas
        respuestas = datos.get("respuestas", [])
        if len(respuestas) != 100:
            return {
                "success": False,
                "error": f"Se esperaban 100 respuestas, se recibieron {len(respuestas)}"
            }
        
        # Convertir None a string vacío para compatibilidad
        respuestas_procesadas = []
        for resp in respuestas:
            if resp is None or resp == "":
                respuestas_procesadas.append("")
            else:
                respuestas_procesadas.append(str(resp).upper())
        
        print(f"\n✅ EXTRACCIÓN COMPLETADA")
        print(f"   Código hoja: {datos.get('codigo_hoja')}")
        print(f"   DNI: {datos.get('dni_postulante')}")
        print(f"   Respuestas: {len(respuestas_procesadas)}/100")
        
        # Contar válidas
        validas = sum(1 for r in respuestas_procesadas if r in ['A','B','C','D','E'])
        print(f"   Válidas: {validas}")
        
        return {
            "success": True,
            "datos": {
                "codigo_hoja": datos.get("codigo_hoja", ""),
                "dni_postulante": datos.get("dni_postulante", ""),
                "respuestas": respuestas_procesadas
            },
            "api": "gemini-structured",
            "modelo": "gemini-2.5-flash",
            "apis_usadas": ["gemini-2.5-flash"]
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# FUNCIONES AUXILIARES (mantener para compatibilidad)
# ============================================================================

async def procesar_y_guardar_respuestas(hoja_respuesta_id: int, resultado_api: Dict, db):
    """Guarda las 100 respuestas"""
    from app.models import Respuesta
    from datetime import datetime
    
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
            confianza=0.95,  # Gemini tiene alta confianza
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