"""
Servicio de calificación de hojas de respuestas
"""

from typing import List, Dict
from app.models import ClaveRespuesta


def calcular_calificacion(
    respuestas_alumno: List,
    proceso_admision: str,
    db
) -> Dict:
    """
    Calcula la nota comparando respuestas del alumno con el gabarito.
    
    Args:
        respuestas_alumno: Lista de 100 respuestas del alumno
        proceso_admision: Proceso de admisión
        db: Sesión de base de datos
        
    Returns:
        Dict con correctas, incorrectas, vacias y nota
    """
    # Obtener gabarito ordenado
    gabarito = db.query(ClaveRespuesta).filter_by(
        proceso_admision=proceso_admision
    ).order_by(ClaveRespuesta.numero_pregunta).all()
    
    if len(gabarito) != 100:
        raise ValueError(f"El gabarito debe tener 100 respuestas, tiene {len(gabarito)}")
    
    correctas = 0
    incorrectas = 0
    vacias = 0
    
    for i, resp_alumno in enumerate(respuestas_alumno):
        resp_correcta = gabarito[i].respuesta_correcta.upper()
        
        if resp_alumno is None or resp_alumno == "":
            vacias += 1
        elif resp_alumno.upper() == resp_correcta:
            correctas += 1
        else:
            incorrectas += 1
    
    # Nota sobre 20
    nota = (correctas / 100) * 20
    
    return {
        "correctas": correctas,
        "incorrectas": incorrectas,
        "vacias": vacias,
        "nota": round(nota, 2)
    }


def gabarito_existe(proceso_admision: str, db) -> bool:
    """
    Verifica si existe gabarito para un proceso de admisión.
    
    Args:
        proceso_admision: Proceso de admisión
        db: Sesión de base de datos
        
    Returns:
        bool: True si existe gabarito completo (100 respuestas)
    """
    count = db.query(ClaveRespuesta).filter_by(
        proceso_admision=proceso_admision
    ).count()
    
    return count == 100