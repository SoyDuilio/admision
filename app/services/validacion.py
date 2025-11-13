"""
Servicio de validación de códigos en base de datos
"""

from typing import Dict, Tuple, List
from app.models import Postulante, Profesor, Aula


def validar_codigos(
    dni_postulante: str,
    dni_profesor: str,
    codigo_aula: str,
    db
) -> Tuple[str, List[str], Dict]:
    """
    Valida que los códigos existan en la base de datos.
    
    Args:
        dni_postulante: DNI del postulante
        dni_profesor: DNI del profesor
        codigo_aula: Código del aula
        db: Sesión de base de datos
        
    Returns:
        Tuple con:
        - estado: "completado", "observado" o "error"
        - mensajes: Lista de mensajes de validación
        - datos: Dict con postulante, profesor y aula encontrados
    """
    errores = []
    mensajes = []
    datos = {
        "postulante": None,
        "profesor": None,
        "aula": None
    }
    
    # Validar DNI postulante
    postulante = db.query(Postulante).filter_by(dni=dni_postulante).first()
    if not postulante:
        errores.append("DNI_POSTULANTE")
        mensajes.append(f"⚠️ DNI postulante {dni_postulante} no registrado")
    else:
        datos["postulante"] = postulante
    
    # Validar DNI profesor
    profesor = db.query(Profesor).filter_by(dni=dni_profesor).first()
    if not profesor:
        errores.append("DNI_PROFESOR")
        mensajes.append(f"⚠️ DNI profesor {dni_profesor} no registrado")
    else:
        datos["profesor"] = profesor
    
    # Validar código aula
    aula = db.query(Aula).filter_by(codigo=codigo_aula).first()
    if not aula:
        errores.append("CODIGO_AULA")
        mensajes.append(f"⚠️ Código aula {codigo_aula} no existe")
    else:
        datos["aula"] = aula
    
    # Determinar estado
    if len(errores) == 0:
        estado = "completado"
        mensajes = ["✅ Hoja validada correctamente"]
    elif len(errores) >= 2:
        estado = "error"
        mensajes.insert(0, "🚨 ALERTA: Múltiples códigos incorrectos")
    else:
        estado = "observado"
    
    return estado, mensajes, datos