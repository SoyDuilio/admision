"""
Servicios de validación
Ubicación: app/services/validacion.py
"""

from typing import Dict, Tuple
from sqlalchemy.orm import Session


def validar_codigos(
    db: Session,
    dni_postulante: str,
    codigo_aula: str,
    dni_profesor: str,
    codigo_hoja: str
) -> Tuple[bool, Dict]:
    """
    Valida que los códigos extraídos existan en la base de datos.
    
    Returns:
        tuple: (es_valido, datos)
    """
    from app.models import Postulante, Aula, Profesor, HojaRespuesta
    
    resultado = {
        "postulante": None,
        "aula": None,
        "profesor": None,
        "errores": []
    }
    
    # Validar postulante
    postulante = db.query(Postulante).filter(Postulante.dni == dni_postulante).first()
    if not postulante:
        resultado["errores"].append(f"Postulante con DNI {dni_postulante} no encontrado")
    else:
        resultado["postulante"] = postulante
    
    # Validar aula
    aula = db.query(Aula).filter(Aula.codigo == codigo_aula).first()
    if not aula:
        resultado["errores"].append(f"Aula {codigo_aula} no encontrada")
    else:
        resultado["aula"] = aula
    
    # Validar profesor
    profesor = db.query(Profesor).filter(Profesor.dni == dni_profesor).first()
    if not profesor:
        resultado["errores"].append(f"Profesor con DNI {dni_profesor} no encontrado")
    else:
        resultado["profesor"] = profesor
    
    # Validar que el código de hoja no esté duplicado
    hoja_existente = db.query(HojaRespuesta).filter(
        HojaRespuesta.codigo_hoja == codigo_hoja
    ).first()
    
    if hoja_existente:
        resultado["errores"].append(f"Código de hoja {codigo_hoja} ya existe")
    
    es_valido = len(resultado["errores"]) == 0
    
    return es_valido, resultado


def validar_respuestas(respuestas: list) -> Tuple[bool, Dict]:
    """
    Valida que las respuestas sean correctas.
    
    Returns:
        tuple: (son_validas, estadisticas)
    """
    if len(respuestas) != 100:
        return False, {
            "error": f"Se esperaban 100 respuestas, se recibieron {len(respuestas)}"
        }
    
    stats = {
        "total": 100,
        "respondidas": 0,
        "en_blanco": 0,
        "validas": 0,
        "invalidas": 0
    }
    
    validas = ["A", "B", "C", "D", "E", None]
    
    for resp in respuestas:
        if resp is None:
            stats["en_blanco"] += 1
        else:
            stats["respondidas"] += 1
            if resp.upper() in ["A", "B", "C", "D", "E"]:
                stats["validas"] += 1
            else:
                stats["invalidas"] += 1
    
    return True, stats