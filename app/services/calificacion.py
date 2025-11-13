"""
Servicios de calificación
Ubicación: app/services/calificacion.py
"""

from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session


def gabarito_existe(db: Session, proceso_admision: str) -> bool:
    """
    Verifica si existe gabarito (clave de respuestas) para un proceso.
    
    Args:
        db: Sesión de base de datos
        proceso_admision: Ej: "2025-2"
        
    Returns:
        bool: True si existe
    """
    from app.models import ClaveRespuesta
    
    count = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso_admision
    ).count()
    
    return count == 100  # Debe haber exactamente 100 respuestas


def obtener_gabarito(db: Session, proceso_admision: str) -> Optional[Dict]:
    """
    Obtiene el gabarito completo de un proceso.
    
    Returns:
        dict: {1: "A", 2: "B", ..., 100: "E"} o None si no existe
    """
    from app.models import ClaveRespuesta
    
    claves = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso_admision
    ).order_by(ClaveRespuesta.numero_pregunta).all()
    
    if len(claves) != 100:
        return None
    
    gabarito = {}
    for clave in claves:
        gabarito[clave.numero_pregunta] = clave.respuesta_correcta
    
    return gabarito


def calcular_calificacion(
    respuestas_alumno: list,
    gabarito: Dict,
    puntaje_correcto: float = 1.0,
    puntaje_incorrecto: float = 0.0,
    puntaje_blanco: float = 0.0
) -> Dict:
    """
    Calcula la calificación de un alumno.
    
    Args:
        respuestas_alumno: Lista de 100 respuestas ["A", None, "B", ...]
        gabarito: Diccionario {1: "A", 2: "B", ...}
        puntaje_correcto: Puntos por respuesta correcta (default: 1.0)
        puntaje_incorrecto: Puntos por respuesta incorrecta (default: 0.0)
        puntaje_blanco: Puntos por respuesta en blanco (default: 0.0)
        
    Returns:
        dict: {
            "correctas": int,
            "incorrectas": int,
            "en_blanco": int,
            "puntaje": float,
            "nota": float (sobre 20),
            "detalle": list
        }
    """
    if len(respuestas_alumno) != 100:
        raise ValueError(f"Se esperaban 100 respuestas, se recibieron {len(respuestas_alumno)}")
    
    correctas = 0
    incorrectas = 0
    en_blanco = 0
    puntaje_total = 0.0
    detalle = []
    
    for i, respuesta_alumno in enumerate(respuestas_alumno, 1):
        respuesta_correcta = gabarito.get(i)
        
        if respuesta_alumno is None:
            # En blanco
            en_blanco += 1
            puntaje_total += puntaje_blanco
            detalle.append({
                "pregunta": i,
                "respuesta_alumno": None,
                "respuesta_correcta": respuesta_correcta,
                "resultado": "en_blanco",
                "puntaje": puntaje_blanco
            })
        elif respuesta_alumno.upper() == respuesta_correcta:
            # Correcta
            correctas += 1
            puntaje_total += puntaje_correcto
            detalle.append({
                "pregunta": i,
                "respuesta_alumno": respuesta_alumno,
                "respuesta_correcta": respuesta_correcta,
                "resultado": "correcta",
                "puntaje": puntaje_correcto
            })
        else:
            # Incorrecta
            incorrectas += 1
            puntaje_total += puntaje_incorrecto
            detalle.append({
                "pregunta": i,
                "respuesta_alumno": respuesta_alumno,
                "respuesta_correcta": respuesta_correcta,
                "resultado": "incorrecta",
                "puntaje": puntaje_incorrecto
            })
    
    # Calcular nota sobre 20
    nota = (correctas / 100) * 20
    
    return {
        "correctas": correctas,
        "incorrectas": incorrectas,
        "en_blanco": en_blanco,
        "puntaje": puntaje_total,
        "nota": round(nota, 2),
        "detalle": detalle
    }