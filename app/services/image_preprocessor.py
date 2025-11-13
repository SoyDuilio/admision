"""
Pre-procesador de imágenes con OpenCV para máxima fidelidad de lectura
Ubicación: app/services/image_preprocessor.py

FUNCIONES:
- Detecta y corrige perspectiva (fotos trapezoidales)
- Mejora iluminación no uniforme (CLAHE)
- Binarización adaptativa
- Aumenta nitidez
- Elimina ruido
"""

import cv2
import numpy as np
from typing import Tuple, Optional
import os


class ImagePreprocessor:
    """
    Pre-procesador de imágenes para hojas de respuestas.
    """
    
    def __init__(self):
        self.min_area = 50000  # Área mínima del marco en píxeles
        self.debug = False  # Cambiar a True para guardar imágenes intermedias
    
    def procesar_completo(self, imagen_path: str) -> Tuple[str, dict]:
        """
        Pipeline completo de pre-procesamiento.
        
        Args:
            imagen_path: Ruta de la imagen original
            
        Returns:
            tuple: (ruta_imagen_procesada, metadata)
        """
        print("🔧 Iniciando pre-procesamiento OpenCV...")
        
        # Cargar imagen
        img = cv2.imread(imagen_path)
        if img is None:
            raise ValueError(f"No se pudo cargar: {imagen_path}")
        
        h, w = img.shape[:2]
        print(f"📐 Original: {w}x{h}px")
        
        metadata = {
            "original_size": f"{w}x{h}",
            "steps": []
        }
        
        # PASO 1: Detectar y corregir perspectiva
        img_warped, warp_ok = self.corregir_perspectiva(img)
        
        if warp_ok:
            img = img_warped
            metadata["steps"].append("perspectiva_corregida")
            print("✅ Perspectiva corregida")
        else:
            metadata["steps"].append("sin_correccion_perspectiva")
            print("ℹ️  Usando imagen original")
        
        # PASO 2: Mejorar iluminación (CLAHE)
        img = self.mejorar_iluminacion(img)
        metadata["steps"].append("iluminacion_mejorada")
        print("✅ Iluminación mejorada")
        
        # PASO 3: Aumentar nitidez
        img = self.aumentar_nitidez(img)
        metadata["steps"].append("nitidez_aumentada")
        print("✅ Nitidez aumentada")
        
        # PASO 4: Binarización adaptativa
        img_binary = self.binarizar_adaptativo(img)
        metadata["steps"].append("binarizado_adaptativo")
        print("✅ Binarizado adaptativo")
        
        # Guardar
        output_path = imagen_path.replace('.jpg', '_processed.jpg').replace('.jpeg', '_processed.jpg').replace('.png', '_processed.png')
        cv2.imwrite(output_path, img_binary, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        h_final, w_final = img_binary.shape[:2]
        metadata["final_size"] = f"{w_final}x{h_final}"
        
        print(f"✅ Guardado: {output_path}")
        
        return output_path, metadata
    
    def corregir_perspectiva(self, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Detecta marco negro y corrige perspectiva.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Detectar bordes
        edged = cv2.Canny(blurred, 50, 200)
        
        # Dilatar para cerrar gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged = cv2.dilate(edged, kernel, iterations=1)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Ordenar por área
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        marco_contour = None
        
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # Buscar rectángulo (4 puntos)
            if len(approx) == 4:
                area = cv2.contourArea(contour)
                if area > self.min_area:
                    marco_contour = approx
                    break
        
        if marco_contour is None:
            return img, False
        
        # Ordenar puntos
        pts = marco_contour.reshape(4, 2)
        rect = self.ordenar_puntos(pts)
        
        # Calcular dimensiones
        (tl, tr, br, bl) = rect
        
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = max(int(heightA), int(heightB))
        
        # Transformación
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
        
        return warped, True
    
    def ordenar_puntos(self, pts: np.ndarray) -> np.ndarray:
        """Ordena: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def mejorar_iluminacion(self, img: np.ndarray) -> np.ndarray:
        """Corrige iluminación no uniforme con CLAHE"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return enhanced
    
    def aumentar_nitidez(self, img: np.ndarray) -> np.ndarray:
        """Aumenta nitidez para texto más legible"""
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        
        sharpened = cv2.filter2D(img, -1, kernel)
        return sharpened
    
    def binarizar_adaptativo(self, img: np.ndarray) -> np.ndarray:
        """Binarización adaptativa (mejor que threshold fijo)"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Binarización adaptativa Gaussiana
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            21,
            10
        )
        
        return binary