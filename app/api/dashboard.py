"""
POSTULANDO - API del Dashboard Principal
app/api/dashboard.py

Endpoint central que provee todas las estadísticas para el dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timedelta

from app.database import get_db
from app.models import (
    Postulante,
    HojaRespuesta,
    Respuesta,
    ClaveRespuesta,
    Calificacion,
    # Nuevos modelos que necesitarás
    # VentaCarpeta,
    # VerificacionCertificado
)

router = APIRouter()


@router.get("/dashboard/estadisticas")
async def obtener_estadisticas_dashboard(
    proceso: str = "ADMISION_2025_2",
    db: Session = Depends(get_db)
):
    """
    Obtiene todas las estadísticas para el dashboard principal.
    
    Returns:
        Dict con estadísticas completas del proceso de admisión
    """
    
    try:
        hoy = datetime.now().date()
        
        # ================================================================
        # MÓDULO 1: POSTULANTES
        # ================================================================
        
        total_postulantes = db.query(Postulante).filter(
            Postulante.activo == True
        ).count()
        
        postulantes_nuevos_hoy = db.query(Postulante).filter(
            and_(
                Postulante.activo == True,
                func.date(Postulante.fecha_registro) == hoy
            )
        ).count()
        
        # ================================================================
        # MÓDULO 2: VENTAS (si existe el modelo)
        # ================================================================
        
        ventas_hoy = 0.0  # TODO: Implementar cuando exista VentaCarpeta
        # ventas_hoy = db.query(func.sum(VentaCarpeta.monto)).filter(
        #     func.date(VentaCarpeta.fecha_venta) == hoy
        # ).scalar() or 0.0
        
        # ================================================================
        # MÓDULO 3: VERIFICACIÓN MINEDU
        # ================================================================
        
        # TODO: Implementar cuando exista VerificacionCertificado
        # Por ahora, simular con campo en Postulante
        sin_certificado_minedu = 0  # Placeholder
        
        # ================================================================
        # MÓDULO 4: HOJAS DE RESPUESTA
        # ================================================================
        
        hojas_procesadas = db.query(HojaRespuesta).filter(
            and_(
                HojaRespuesta.proceso_admision == proceso,
                HojaRespuesta.estado.in_(["completado", "calificado"])
            )
        ).count()
        
        hojas_pendientes = db.query(HojaRespuesta).filter(
            and_(
                HojaRespuesta.proceso_admision == proceso,
                HojaRespuesta.estado == "generada"
            )
        ).count()
        
        hojas_calificadas = db.query(HojaRespuesta).filter(
            and_(
                HojaRespuesta.proceso_admision == proceso,
                HojaRespuesta.estado == "calificado"
            )
        ).count()
        
        # ================================================================
        # MÓDULO 5: RESPUESTAS QUE REQUIEREN REVISIÓN
        # ================================================================
        
        # Contar respuestas con confianza < 0.95 y que no están vacías
        requieren_revision = db.query(Respuesta).join(HojaRespuesta).filter(
            and_(
                HojaRespuesta.proceso_admision == proceso,
                Respuesta.confianza < 0.95,
                Respuesta.confianza.isnot(None),
                Respuesta.respuesta_marcada != ""
            )
        ).count()
        
        # ================================================================
        # MÓDULO 6: GABARITO
        # ================================================================
        
        gabarito_registrado = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == proceso
        ).count() == 100
        
        # ================================================================
        # MÓDULO 7: CALIFICACIÓN
        # ================================================================
        
        calificaciones = db.query(Calificacion).filter(
            Calificacion.nota.isnot(None)
        ).all()
        
        if calificaciones:
            notas = [c.nota for c in calificaciones]
            nota_promedio = sum(notas) / len(notas)
            aprobados = sum(1 for c in calificaciones if c.aprobado)
            desaprobados = len(calificaciones) - aprobados
        else:
            nota_promedio = 0
            aprobados = 0
            desaprobados = 0
        
        calificacion_completada = hojas_calificadas > 0 and hojas_calificadas == hojas_procesadas
        
        # ================================================================
        # RESUMEN GENERAL
        # ================================================================
        
        estadisticas = {
            "success": True,
            "proceso": proceso,
            "fecha_consulta": datetime.now().isoformat(),
            
            # Postulantes
            "total_postulantes": total_postulantes,
            "postulantes_nuevos_hoy": postulantes_nuevos_hoy,
            
            # Ventas
            "ventas_hoy": ventas_hoy,
            
            # Verificación MINEDU
            "sin_certificado_minedu": sin_certificado_minedu,
            
            # Hojas
            "hojas_procesadas": hojas_procesadas,
            "hojas_pendientes": hojas_pendientes,
            "hojas_calificadas": hojas_calificadas,
            
            # Revisión manual
            "requieren_revision": requieren_revision,
            
            # Gabarito
            "gabarito_registrado": gabarito_registrado,
            
            # Calificación
            "nota_promedio": round(nota_promedio, 2),
            "aprobados": aprobados,
            "desaprobados": desaprobados,
            "calificacion_completada": calificacion_completada,
            
            # Estados de módulos
            "modulos": {
                "registro": "activo",
                "verificacion": "pendiente" if sin_certificado_minedu > 0 else "activo",
                "asignacion": "activo",
                "generacion_hojas": "activo",
                "captura": "activo",
                "gabarito": "completado" if gabarito_registrado else "pendiente",
                "correccion": "pendiente" if requieren_revision > 0 else "activo",
                "calificacion": "completado" if calificacion_completada else "pendiente",
                "publicacion": "listo" if calificacion_completada else "bloqueado",
                "registra": "desarrollo"
            }
        }
        
        return estadisticas
        
    except Exception as e:
        print(f"❌ Error en dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/resumen-proceso")
async def resumen_proceso(
    proceso: str = "ADMISION_2025_2",
    db: Session = Depends(get_db)
):
    """
    Resumen ejecutivo del proceso de admisión.
    """
    
    try:
        # Postulantes por programa
        postulantes_por_programa = db.query(
            Postulante.programa_educativo,
            func.count(Postulante.id).label('total')
        ).filter(
            Postulante.activo == True
        ).group_by(
            Postulante.programa_educativo
        ).all()
        
        # Hojas por estado
        hojas_por_estado = db.query(
            HojaRespuesta.estado,
            func.count(HojaRespuesta.id).label('total')
        ).filter(
            HojaRespuesta.proceso_admision == proceso
        ).group_by(
            HojaRespuesta.estado
        ).all()
        
        # Calificaciones
        total_calificados = db.query(Calificacion).count()
        
        return {
            "success": True,
            "proceso": proceso,
            "postulantes_por_programa": [
                {"programa": p[0], "total": p[1]} 
                for p in postulantes_por_programa
            ],
            "hojas_por_estado": [
                {"estado": e[0], "total": e[1]} 
                for e in hojas_por_estado
            ],
            "total_calificados": total_calificados
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/alertas")
async def obtener_alertas(
    proceso: str = "ADMISION_2025_2",
    db: Session = Depends(get_db)
):
    """
    Obtiene alertas críticas que requieren atención inmediata.
    """
    
    alertas = []
    
    try:
        # Alerta 1: Certificados no registrados
        sin_certificado = 0  # TODO: Implementar
        if sin_certificado > 0:
            alertas.append({
                "tipo": "critical",
                "titulo": "Postulantes sin certificado MINEDU",
                "mensaje": f"{sin_certificado} postulantes con certificado no registrado en MINEDU",
                "accion": "/postulantes/sin-certificado",
                "icono": "⚠️"
            })
        
        # Alerta 2: Hojas pendientes de revisión
        requieren_revision = db.query(Respuesta).join(HojaRespuesta).filter(
            and_(
                HojaRespuesta.proceso_admision == proceso,
                Respuesta.confianza < 0.95,
                Respuesta.confianza.isnot(None)
            )
        ).count()
        
        if requieren_revision > 0:
            alertas.append({
                "tipo": "warning",
                "titulo": "Respuestas requieren revisión manual",
                "mensaje": f"{requieren_revision} respuestas con confianza < 95%",
                "accion": "/revision-manual",
                "icono": "✏️"
            })
        
        # Alerta 3: Gabarito pendiente
        gabarito_existe = db.query(ClaveRespuesta).filter(
            ClaveRespuesta.proceso_admision == proceso
        ).count() == 100
        
        if not gabarito_existe:
            hojas_procesadas = db.query(HojaRespuesta).filter(
                and_(
                    HojaRespuesta.proceso_admision == proceso,
                    HojaRespuesta.estado == "completado"
                )
            ).count()
            
            if hojas_procesadas > 10:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Gabarito pendiente",
                    "mensaje": f"Hay {hojas_procesadas} hojas procesadas esperando gabarito para calificación",
                    "accion": "/registrar-gabarito",
                    "icono": "📋"
                })
        
        return {
            "success": True,
            "alertas": alertas
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))