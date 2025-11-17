"""
POSTULANDO - Servicio de Calificación Automática
app/services/calificacion_service.py

Califica hojas de respuestas comparándolas con el gabarito oficial.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Dict, List, Optional
import json

from app.models import (
    HojaRespuesta,
    Respuesta,
    ClaveRespuesta,
    Calificacion,
    Postulante
)


def obtener_gabarito(proceso_admision: str, db: Session) -> Optional[Dict[str, str]]:
    """
    Obtiene el gabarito oficial para un proceso de admisión.
    
    Returns:
        Dict con {numero_pregunta: respuesta_correcta}
        Ej: {"1": "A", "2": "B", ...}
    """
    
    claves = db.query(ClaveRespuesta).filter(
        ClaveRespuesta.proceso_admision == proceso_admision
    ).order_by(ClaveRespuesta.numero_pregunta).all()
    
    if not claves:
        return None
    
    gabarito = {}
    for clave in claves:
        gabarito[str(clave.numero_pregunta)] = clave.respuesta_correcta.upper()
    
    return gabarito


def calificar_hoja_individual(
    hoja_id: int,
    gabarito: Dict[str, str],
    db: Session
) -> Dict:
    """
    Califica una hoja individual de respuestas.
    
    Args:
        hoja_id: ID de la hoja a calificar
        gabarito: Diccionario con respuestas correctas
        db: Sesión de base de datos
    
    Returns:
        Dict con estadísticas de calificación
    """
    
    # Obtener hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        raise ValueError(f"Hoja {hoja_id} no encontrada")
    
    # Obtener respuestas
    respuestas = db.query(Respuesta).filter(
        Respuesta.hoja_respuesta_id == hoja_id
    ).order_by(Respuesta.numero_pregunta).all()
    
    if not respuestas or len(respuestas) != 100:
        raise ValueError(f"La hoja {hoja_id} no tiene 100 respuestas")
    
    # Contadores
    correctas = 0
    incorrectas = 0
    en_blanco = 0
    invalidas = 0
    
    # Calificar cada respuesta
    for respuesta in respuestas:
        num_pregunta = str(respuesta.numero_pregunta)
        respuesta_correcta = gabarito.get(num_pregunta)
        
        if not respuesta_correcta:
            continue  # Pregunta no está en gabarito
        
        respuesta_marcada = respuesta.respuesta_marcada.strip().upper()
        
        # Clasificar respuesta
        if respuesta_marcada == "":
            # Vacía
            en_blanco += 1
            respuesta.es_correcta = False
        elif respuesta_marcada in ['A', 'B', 'C', 'D', 'E']:
            # Válida
            if respuesta_marcada == respuesta_correcta:
                correctas += 1
                respuesta.es_correcta = True
            else:
                incorrectas += 1
                respuesta.es_correcta = False
        else:
            # Inválida (?, GARABATO, MULTIPLE, etc.)
            invalidas += 1
            respuesta.es_correcta = False
    
    # Calcular nota
    total_preguntas = len(respuestas)
    porcentaje = (correctas / total_preguntas) * 100 if total_preguntas > 0 else 0
    
    # Sistema vigesimal peruano (0-20)
    nota_vigesimal = (correctas / total_preguntas) * 20 if total_preguntas > 0 else 0
    nota_vigesimal = round(nota_vigesimal, 2)
    
    # Nota mínima de aprobación (generalmente 10.5 en Perú)
    nota_minima = 10.5
    aprobado = nota_vigesimal >= nota_minima
    
    # Actualizar hoja
    hoja.nota_final = nota_vigesimal
    hoja.respuestas_correctas_count = correctas
    hoja.estado = "calificado"
    hoja.fecha_calificacion = datetime.now()
    
    # Actualizar o crear calificación
    calificacion = db.query(Calificacion).filter(
        Calificacion.postulante_id == hoja.postulante_id
    ).first()
    
    if calificacion:
        # Actualizar existente
        calificacion.nota = int(nota_vigesimal)
        calificacion.correctas = correctas
        calificacion.incorrectas = incorrectas
        calificacion.en_blanco = en_blanco
        calificacion.no_legibles = invalidas
        calificacion.porcentaje_aciertos = round(porcentaje, 2)
        calificacion.aprobado = aprobado
        calificacion.nota_minima = int(nota_minima)
        calificacion.calificado_at = datetime.now()
    else:
        # Crear nueva
        calificacion = Calificacion(
            postulante_id=hoja.postulante_id,
            nota=int(nota_vigesimal),
            correctas=correctas,
            incorrectas=incorrectas,
            en_blanco=en_blanco,
            no_legibles=invalidas,
            porcentaje_aciertos=round(porcentaje, 2),
            aprobado=aprobado,
            nota_minima=int(nota_minima),
            calificado_at=datetime.now()
        )
        db.add(calificacion)
    
    # Commit
    db.commit()
    
    return {
        "hoja_id": hoja_id,
        "codigo_hoja": hoja.codigo_hoja,
        "postulante_id": hoja.postulante_id,
        "nota_final": nota_vigesimal,
        "correctas": correctas,
        "incorrectas": incorrectas,
        "en_blanco": en_blanco,
        "invalidas": invalidas,
        "total": total_preguntas,
        "porcentaje": round(porcentaje, 2),
        "aprobado": aprobado
    }


def calificar_hojas_pendientes(
    proceso_admision: str,
    db: Session,
    limite: Optional[int] = None
) -> Dict:
    """
    Califica todas las hojas pendientes de un proceso.
    
    Args:
        proceso_admision: Código del proceso
        db: Sesión de base de datos
        limite: Opcional, limitar cantidad de hojas a calificar
    
    Returns:
        Dict con resumen de calificación
    """
    
    print("\n" + "="*70)
    print("🎯 INICIANDO CALIFICACIÓN AUTOMÁTICA")
    print("="*70)
    
    # Obtener gabarito
    gabarito = obtener_gabarito(proceso_admision, db)
    
    if not gabarito:
        raise ValueError(f"No existe gabarito para el proceso {proceso_admision}")
    
    print(f"✅ Gabarito cargado: {len(gabarito)} respuestas")
    
    # Obtener hojas pendientes
    query = db.query(HojaRespuesta).filter(
        and_(
            HojaRespuesta.proceso_admision == proceso_admision,
            HojaRespuesta.estado.in_(["completado", "pendiente_calificar"])
        )
    )
    
    if limite:
        query = query.limit(limite)
    
    hojas_pendientes = query.all()
    
    if not hojas_pendientes:
        return {
            "success": True,
            "mensaje": "No hay hojas pendientes de calificar",
            "calificadas": 0,
            "errores": []
        }
    
    print(f"📋 Hojas pendientes: {len(hojas_pendientes)}")
    print("="*70)
    
    # Calificar cada hoja
    resultados = []
    errores = []
    
    for i, hoja in enumerate(hojas_pendientes, 1):
        try:
            print(f"\n[{i}/{len(hojas_pendientes)}] Calificando hoja {hoja.codigo_hoja}...")
            
            resultado = calificar_hoja_individual(hoja.id, gabarito, db)
            resultados.append(resultado)
            
            print(f"✅ Nota: {resultado['nota_final']}/20")
            print(f"   Correctas: {resultado['correctas']}, "
                  f"Incorrectas: {resultado['incorrectas']}, "
                  f"En blanco: {resultado['en_blanco']}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            errores.append({
                "hoja_id": hoja.id,
                "codigo_hoja": hoja.codigo_hoja,
                "error": str(e)
            })
    
    # Calcular estadísticas generales
    if resultados:
        notas = [r["nota_final"] for r in resultados]
        nota_promedio = sum(notas) / len(notas)
        nota_maxima = max(notas)
        nota_minima = min(notas)
        aprobados = sum(1 for r in resultados if r["aprobado"])
        desaprobados = len(resultados) - aprobados
    else:
        nota_promedio = 0
        nota_maxima = 0
        nota_minima = 0
        aprobados = 0
        desaprobados = 0
    
    print("\n" + "="*70)
    print("📊 RESUMEN DE CALIFICACIÓN")
    print("="*70)
    print(f"✅ Hojas calificadas: {len(resultados)}")
    print(f"❌ Errores: {len(errores)}")
    print(f"📈 Nota promedio: {nota_promedio:.2f}/20")
    print(f"🏆 Nota máxima: {nota_maxima:.2f}/20")
    print(f"📉 Nota mínima: {nota_minima:.2f}/20")
    print(f"✅ Aprobados: {aprobados}")
    print(f"❌ Desaprobados: {desaprobados}")
    print("="*70)
    
    # Calcular orden de mérito
    actualizar_orden_merito(proceso_admision, db)
    
    return {
        "success": True,
        "calificadas": len(resultados),
        "errores": errores,
        "estadisticas": {
            "nota_promedio": round(nota_promedio, 2),
            "nota_maxima": round(nota_maxima, 2),
            "nota_minima": round(nota_minima, 2),
            "aprobados": aprobados,
            "desaprobados": desaprobados,
            "total": len(resultados)
        },
        "resultados": resultados
    }


def actualizar_orden_merito(proceso_admision: str, db: Session):
    """
    Actualiza el orden de mérito (puestos) de los postulantes.
    Ordena por nota descendente y asigna puestos.
    """
    
    print("\n📊 Calculando orden de mérito...")
    
    # Obtener todas las calificaciones con nota
    calificaciones = db.query(Calificacion).filter(
        Calificacion.nota.isnot(None)
    ).order_by(
        Calificacion.nota.desc(),
        Calificacion.correctas.desc()  # Desempate por correctas
    ).all()
    
    # Asignar puestos
    for puesto, calificacion in enumerate(calificaciones, start=1):
        calificacion.puesto = puesto
    
    db.commit()
    
    print(f"✅ Orden de mérito actualizado: {len(calificaciones)} postulantes")


def obtener_estadisticas_calificacion(proceso_admision: str, db: Session) -> Dict:
    """
    Obtiene estadísticas de calificación de un proceso.
    """
    
    # Hojas totales
    total_hojas = db.query(HojaRespuesta).filter(
        HojaRespuesta.proceso_admision == proceso_admision
    ).count()
    
    # Hojas calificadas
    hojas_calificadas = db.query(HojaRespuesta).filter(
        and_(
            HojaRespuesta.proceso_admision == proceso_admision,
            HojaRespuesta.estado == "calificado"
        )
    ).count()
    
    # Hojas pendientes
    hojas_pendientes = total_hojas - hojas_calificadas
    
    # Calificaciones
    calificaciones = db.query(Calificacion).filter(
        Calificacion.nota.isnot(None)
    ).all()
    
    if calificaciones:
        notas = [c.nota for c in calificaciones]
        aprobados = sum(1 for c in calificaciones if c.aprobado)
        
        estadisticas = {
            "total_hojas": total_hojas,
            "hojas_calificadas": hojas_calificadas,
            "hojas_pendientes": hojas_pendientes,
            "porcentaje_calificadas": round((hojas_calificadas / total_hojas * 100), 2) if total_hojas > 0 else 0,
            "nota_promedio": round(sum(notas) / len(notas), 2),
            "nota_maxima": max(notas),
            "nota_minima": min(notas),
            "aprobados": aprobados,
            "desaprobados": len(calificaciones) - aprobados,
            "tasa_aprobacion": round((aprobados / len(calificaciones) * 100), 2) if calificaciones else 0
        }
    else:
        estadisticas = {
            "total_hojas": total_hojas,
            "hojas_calificadas": 0,
            "hojas_pendientes": total_hojas,
            "porcentaje_calificadas": 0,
            "nota_promedio": 0,
            "nota_maxima": 0,
            "nota_minima": 0,
            "aprobados": 0,
            "desaprobados": 0,
            "tasa_aprobacion": 0
        }
    
    return estadisticas


def recalificar_hoja(hoja_id: int, db: Session) -> Dict:
    """
    Recalifica una hoja específica (útil después de correcciones manuales).
    """
    
    # Obtener proceso de la hoja
    hoja = db.query(HojaRespuesta).filter(HojaRespuesta.id == hoja_id).first()
    
    if not hoja:
        raise ValueError(f"Hoja {hoja_id} no encontrada")
    
    # Obtener gabarito
    gabarito = obtener_gabarito(hoja.proceso_admision, db)
    
    if not gabarito:
        raise ValueError(f"No existe gabarito para el proceso {hoja.proceso_admision}")
    
    # Calificar
    return calificar_hoja_individual(hoja_id, gabarito, db)