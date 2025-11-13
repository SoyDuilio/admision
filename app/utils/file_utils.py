"""
Utilidades para manejo de archivos
"""

from pathlib import Path
import uuid
import shutil
from fastapi import UploadFile


def guardar_foto_temporal(file: UploadFile) -> tuple:
    """
    Guarda la foto temporalmente en el servidor.
    
    Args:
        file: Archivo subido por FastAPI
        
    Returns:
        tuple: (filepath, filename)
    """
    # Crear directorio temporal si no existe
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    # Generar nombre único
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = temp_dir / filename
    
    # Guardar archivo
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return str(filepath), filename


def crear_directorio_capturas():
    """Crea el directorio para hojas capturadas si no existe"""
    Path("app/hojas_capturadas").mkdir(parents=True, exist_ok=True)


def crear_directorio_generadas():
    """Crea el directorio para hojas generadas si no existe"""
    Path("hojas_generadas").mkdir(parents=True, exist_ok=True)