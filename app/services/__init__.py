"""
POSTULANDO - Services __init__.py
app/services/__init__.py

Exporta todos los servicios para fácil importación
"""

# ============================================================================
# SERVICIOS DE AUTENTICACIÓN
# ============================================================================
try:
    from app.services.auth_admin import (
        verificar_sesion_admin,
        crear_sesion_admin,
        cerrar_sesion_admin,
        obtener_usuario_actual
    )
except ImportError:
    pass

# ============================================================================
# SERVICIOS DE CALIFICACIÓN
# ============================================================================
try:
    from app.services.calificacion import CalificacionService
except ImportError:
    pass

# ============================================================================
# FUNCIONES LEGACY (para compatibilidad con código existente)
# ============================================================================
try:
    # Si necesitas mantener las funciones antiguas, créalas como wrappers
    from sqlalchemy.orm import Session
    
    def calcular_calificacion(db: Session, hoja_id: int, proceso: str):
        """Wrapper legacy para CalificacionService"""
        servicio = CalificacionService(db)
        return servicio.calificar_hoja(hoja_id, proceso)
    
    def gabarito_existe(db: Session, proceso: str) -> bool:
        """Wrapper legacy para verificar gabarito"""
        servicio = CalificacionService(db)
        return servicio.verificar_gabarito_completo(proceso)
    
except ImportError:
    pass

# ============================================================================
# OTROS SERVICIOS (mantén tus importaciones existentes)
# ============================================================================
# Ejemplo:
# from app.services.pdf_generator import generar_pdf
# from app.services.vision import procesar_imagen
# etc.