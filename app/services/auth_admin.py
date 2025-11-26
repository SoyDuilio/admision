"""
POSTULANDO - Servicio de Autenticación Admin
app/services/auth_admin.py

Manejo de:
- Sesiones de administradores
- Verificación de permisos
- Tokens de acceso
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, Request, Depends, status
from typing import Optional
import secrets
import hashlib
from datetime import datetime, timedelta

from app.database import get_db


def crear_sesion_admin(db: Session, usuario_id: int, remember: bool = False) -> str:
    """
    Crea una nueva sesión para un administrador.
    
    Args:
        db: Sesión de base de datos
        usuario_id: ID del usuario
        remember: Si debe recordar la sesión por más tiempo
        
    Returns:
        Token de sesión
    """
    # Generar token único
    token = secrets.token_urlsafe(32)
    
    # Calcular fecha de expiración
    if remember:
        expira = datetime.now() + timedelta(days=30)
    else:
        expira = datetime.now() + timedelta(hours=8)
    
    # Guardar sesión
    db.execute(text("""
        INSERT INTO sesiones_admin (token, usuario_id, expira_at, created_at)
        VALUES (:token, :usuario_id, :expira, NOW())
    """), {
        "token": hashlib.sha256(token.encode()).hexdigest(),
        "usuario_id": usuario_id,
        "expira": expira
    })
    
    db.commit()
    
    return token


def verificar_sesion_admin(db: Session, token: str) -> Optional[dict]:
    """
    Verifica si un token de sesión es válido.
    
    Args:
        db: Sesión de base de datos
        token: Token de sesión
        
    Returns:
        Datos del usuario si el token es válido, None si no
    """
    if not token:
        return None
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    result = db.execute(text("""
        SELECT 
            ua.id,
            ua.username,
            ua.nombres,
            ua.apellidos,
            ua.email,
            ua.rol,
            ua.cargo,
            ua.foto_url,
            sa.expira_at
        FROM sesiones_admin sa
        JOIN usuarios_admin ua ON ua.id = sa.usuario_id
        WHERE sa.token = :token
        AND sa.expira_at > NOW()
        AND ua.activo = true
    """), {"token": token_hash}).fetchone()
    
    if not result:
        return None
    
    return {
        "id": result.id,
        "username": result.username,
        "nombres": result.nombres,
        "apellidos": result.apellidos,
        "email": result.email,
        "rol": result.rol,
        "cargo": result.cargo,
        "foto_url": result.foto_url
    }


def cerrar_sesion_admin(db: Session, token: str):
    """
    Cierra una sesión de administrador.
    
    Args:
        db: Sesión de base de datos
        token: Token de sesión
    """
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db.execute(text("""
            DELETE FROM sesiones_admin WHERE token = :token
        """), {"token": token_hash})
        db.commit()


async def obtener_usuario_actual(
    request: Request,
    db: Session = Depends(get_db)
) -> dict:
    """
    Dependencia de FastAPI para obtener el usuario actual.
    
    Verifica la cookie de sesión y retorna los datos del usuario.
    Redirige al login si no hay sesión válida.
    """
    token = request.cookies.get("admin_session")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    
    usuario = verificar_sesion_admin(db, token)
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    
    return usuario


def verificar_permiso(usuario: dict, permisos_requeridos: list) -> bool:
    """
    Verifica si un usuario tiene los permisos necesarios.
    
    Args:
        usuario: Datos del usuario
        permisos_requeridos: Lista de roles permitidos
        
    Returns:
        True si tiene permiso, False si no
    """
    return usuario.get("rol") in permisos_requeridos


def requiere_rol(*roles):
    """
    Decorador para verificar roles en endpoints.
    
    Uso:
        @router.get("/secreto")
        @requiere_rol("RECTOR", "DIRECTOR")
        async def endpoint_secreto(...):
    """
    def decorator(func):
        async def wrapper(*args, usuario: dict = Depends(obtener_usuario_actual), **kwargs):
            if usuario.get("rol") not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tiene permisos para realizar esta acción"
                )
            return await func(*args, usuario=usuario, **kwargs)
        return wrapper
    return decorator


def limpiar_sesiones_expiradas(db: Session):
    """
    Elimina sesiones expiradas de la base de datos.
    Puede ejecutarse como tarea programada.
    """
    db.execute(text("""
        DELETE FROM sesiones_admin WHERE expira_at < NOW()
    """))
    db.commit()