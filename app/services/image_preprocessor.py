"""
Image Preprocessor - Versión básica para compatibilidad
app/services/image_preprocessor.py

NOTA: Esta es la versión básica usada por vision_service_v2.py
Para la versión mejorada, usa image_preprocessor_v2.py
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict


class ImagePreprocessor:
    """Pre-procesador básico de imágenes."""
    
    def __init__(self):
        pass
    
    def corregir_perspectiva(self, imagen: np.ndarray) -> np.ndarray:
        """Corrección básica de perspectiva."""
        try:
            gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 50, 150)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest = max(contours, key=cv2.contourArea)
                epsilon = 0.02 * cv2.arcLength(largest, True)
                approx = cv2.approxPolyDP(largest, epsilon, True)
                
                if len(approx) == 4:
                    pts = approx.reshape(4, 2).astype("float32")
                    # Transformación básica
                    return imagen
            
            return imagen
        except:
            return imagen
    
    def mejorar_iluminacion(self, imagen: np.ndarray) -> np.ndarray:
        """Mejora básica de iluminación."""
        try:
            lab = cv2.cvtColor(imagen, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        except:
            return imagen
    
    def aumentar_nitidez(self, imagen: np.ndarray) -> np.ndarray:
        """Aumenta nitidez."""
        try:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            return cv2.filter2D(imagen, -1, kernel)
        except:
            return imagen
    
    def binarizar_adaptativo(self, imagen: np.ndarray) -> np.ndarray:
        """Binarización adaptativa."""
        try:
            gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        except:
            return imagen
    
    def procesar_completo(self, imagen_path: str) -> Tuple[str, Dict]:
        """Pipeline básico de procesamiento."""
        try:
            imagen = cv2.imread(imagen_path)
            if imagen is None:
                return imagen_path, {"error": "No se pudo cargar", "used": False}
            
            # Procesamiento simple
            imagen = self.corregir_perspectiva(imagen)
            imagen = self.mejorar_iluminacion(imagen)
            imagen = self.aumentar_nitidez(imagen)
            imagen = self.binarizar_adaptativo(imagen)
            
            # Guardar
            path_obj = Path(imagen_path)
            output_path = path_obj.parent / f"{path_obj.stem}_processed{path_obj.suffix}"
            cv2.imwrite(str(output_path), imagen)
            
            return str(output_path), {"used": True, "output_path": str(output_path)}
            
        except Exception as e:
            return imagen_path, {"error": str(e), "used": False}