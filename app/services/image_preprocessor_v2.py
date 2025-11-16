"""
Image Preprocessor V2 - Optimizado para Hojas de Respuestas
app/services/image_preprocessor_v2.py

MEJORAS V2:
- Aumento de contraste más agresivo (CLAHE)
- Binarización adaptativa optimizada para texto manuscrito
- Detección y corrección de perspectiva mejorada
- Reducción de sombras
- Nitidez enfocada en áreas de texto
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import os


class ImagePreprocessorV2:
    """
    Pre-procesador de imágenes optimizado para hojas de examen.
    """
    
    def __init__(self):
        self.debug_mode = False
    
    def corregir_perspectiva(self, imagen: np.ndarray) -> np.ndarray:
        """
        Detecta y corrige la perspectiva de la hoja.
        """
        try:
            gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 50, 150, apertureSize=3)
            
            # Detectar líneas
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            
            if lines is not None and len(lines) > 4:
                # Intentar encontrar el contorno del documento
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Encontrar el contorno más grande (debería ser la hoja)
                    largest_contour = max(contours, key=cv2.contourArea)
                    
                    # Aproximar el contorno a un polígono
                    epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                    approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                    
                    # Si es un cuadrilátero, aplicar corrección de perspectiva
                    if len(approx) == 4:
                        pts = approx.reshape(4, 2)
                        rect = self._order_points(pts)
                        warped = self._four_point_transform(imagen, rect)
                        return warped
            
            return imagen
            
        except Exception as e:
            print(f"⚠️  Error en corrección de perspectiva: {e}")
            return imagen
    
    def _order_points(self, pts):
        """Ordena puntos en orden: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")
        
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def _four_point_transform(self, image, rect):
        """Aplica transformación de perspectiva"""
        (tl, tr, br, bl) = rect
        
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
    def mejorar_contraste_clahe(self, imagen: np.ndarray) -> np.ndarray:
        """
        Mejora el contraste usando CLAHE (Contrast Limited Adaptive Histogram Equalization).
        Mucho mejor que ecualización simple para documentos.
        """
        try:
            # Convertir a LAB para trabajar solo en luminancia
            lab = cv2.cvtColor(imagen, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Aplicar CLAHE en el canal L (luminancia)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_clahe = clahe.apply(l)
            
            # Recombinar canales
            lab_clahe = cv2.merge([l_clahe, a, b])
            imagen_mejorada = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
            
            return imagen_mejorada
            
        except Exception as e:
            print(f"⚠️  Error en CLAHE: {e}")
            return imagen
    
    def reducir_sombras(self, imagen: np.ndarray) -> np.ndarray:
        """
        Reduce sombras usando división de imagen por background estimado.
        """
        try:
            # Convertir a escala de grises
            gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            
            # Estimar background usando desenfoque grande
            background = cv2.GaussianBlur(gray, (51, 51), 0)
            
            # Dividir para normalizar iluminación
            normalized = cv2.divide(gray, background, scale=255)
            
            # Convertir de vuelta a BGR
            imagen_sin_sombras = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
            
            return imagen_sin_sombras
            
        except Exception as e:
            print(f"⚠️  Error en reducción de sombras: {e}")
            return imagen
    
    def aumentar_nitidez(self, imagen: np.ndarray) -> np.ndarray:
        """
        Aumenta la nitidez usando kernel de realce.
        """
        try:
            # Kernel de nitidez más agresivo
            kernel = np.array([
                [-1, -1, -1],
                [-1,  9, -1],
                [-1, -1, -1]
            ])
            
            sharpened = cv2.filter2D(imagen, -1, kernel)
            
            return sharpened
            
        except Exception as e:
            print(f"⚠️  Error en nitidez: {e}")
            return imagen
    
    def binarizar_adaptativo(self, imagen: np.ndarray) -> np.ndarray:
        """
        Binarización adaptativa optimizada para texto manuscrito.
        """
        try:
            # Convertir a escala de grises
            gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            
            # Binarización adaptativa con parámetros optimizados
            # blockSize más grande para capturar mejor las marcas
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=21,  # Aumentado de 11 a 21
                C=10  # Aumentado de 2 a 10
            )
            
            # Convertir de vuelta a BGR
            binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            
            return binary_bgr
            
        except Exception as e:
            print(f"⚠️  Error en binarización: {e}")
            return imagen
    
    def procesar_completo(self, imagen_path: str) -> Tuple[str, Dict]:
        """
        Pipeline completo de pre-procesamiento V2 con ZOOM 2X.
        
        Orden optimizado:
        1. ZOOM 2X (primero, para mayor resolución)
        2. Reducir sombras
        3. Corregir perspectiva
        4. Mejorar contraste (CLAHE)
        5. Aumentar nitidez
        6. Threshold Otsu
        
        Args:
            imagen_path: Ruta de la imagen original
            
        Returns:
            tuple: (ruta_imagen_procesada, metadata)
        """
        
        print("🔧 Iniciando pre-procesamiento OpenCV V2 + ZOOM 2X...")
        
        try:
            # Cargar imagen
            imagen = cv2.imread(imagen_path)
            
            if imagen is None:
                raise ValueError(f"No se pudo cargar la imagen: {imagen_path}")
            
            h, w = imagen.shape[:2]
            print(f"📐 Original: {w}x{h}px")
            
            # Pipeline de procesamiento
            metadata = {
                "original_size": (w, h),
                "pasos_aplicados": []
            }
            
            # ================================================================
            # PASO 0: ZOOM 2X (NUEVO)
            # ================================================================
            nuevo_ancho = int(w * 2)
            nuevo_alto = int(h * 2)
            
            # Interpolación bicúbica para mejor calidad
            imagen = cv2.resize(
                imagen, 
                (nuevo_ancho, nuevo_alto), 
                interpolation=cv2.INTER_CUBIC
            )
            
            metadata["pasos_aplicados"].append("zoom_2x")
            metadata["zoom_size"] = (nuevo_ancho, nuevo_alto)
            print(f"✅ Zoom 2x aplicado: {nuevo_ancho}x{nuevo_alto}px")
            
            # ================================================================
            # PASO 1: Reducir sombras
            # ================================================================
            imagen = self.reducir_sombras(imagen)
            metadata["pasos_aplicados"].append("reduccion_sombras")
            print("✅ Sombras reducidas")
            
            # ================================================================
            # PASO 2: Corregir perspectiva
            # ================================================================
            imagen = self.corregir_perspectiva(imagen)
            metadata["pasos_aplicados"].append("correccion_perspectiva")
            print("✅ Perspectiva corregida")
            
            # ================================================================
            # PASO 3: Mejorar contraste con CLAHE (más agresivo)
            # ================================================================
            try:
                lab = cv2.cvtColor(imagen, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                
                # CLAHE más agresivo para zoom
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
                l_clahe = clahe.apply(l)
                
                lab_clahe = cv2.merge([l_clahe, a, b])
                imagen = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
                
                metadata["pasos_aplicados"].append("clahe_agresivo")
                print("✅ Contraste mejorado (CLAHE agresivo)")
            except Exception as e:
                print(f"⚠️  CLAHE falló: {e}")
            
            # ================================================================
            # PASO 4: Aumentar nitidez (más agresivo)
            # ================================================================
            try:
                # Kernel de nitidez más fuerte
                kernel = np.array([
                    [-1, -1, -1],
                    [-1, 10, -1],  # Centro más fuerte
                    [-1, -1, -1]
                ])
                
                imagen = cv2.filter2D(imagen, -1, kernel)
                metadata["pasos_aplicados"].append("nitidez_agresiva")
                print("✅ Nitidez aumentada (agresiva)")
            except Exception as e:
                print(f"⚠️  Nitidez falló: {e}")
            
            # ================================================================
            # PASO 5: Threshold Otsu
            # ================================================================
            try:
                gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
                
                # Otsu threshold
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Convertir de vuelta a BGR
                imagen_final = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                
                metadata["pasos_aplicados"].append("threshold_otsu")
                print("✅ Threshold Otsu aplicado")
            except Exception as e:
                print(f"⚠️  Threshold falló: {e}")
                imagen_final = imagen
            
            # ================================================================
            # GUARDAR
            # ================================================================
            path_obj = Path(imagen_path)
            output_dir = path_obj.parent
            output_filename = f"{path_obj.stem}_processed_v2_zoom2x{path_obj.suffix}"
            output_path = output_dir / output_filename
            
            cv2.imwrite(str(output_path), imagen_final)
            
            metadata["output_path"] = str(output_path)
            metadata["output_size"] = imagen_final.shape[:2]
            
            print(f"✅ Guardado: {output_path}")
            
            final_h, final_w = imagen_final.shape[:2]
            print(f"📐 Final: {final_w}x{final_h}px")
            
            return str(output_path), metadata
            
        except Exception as e:
            print(f"❌ Error en pre-procesamiento: {e}")
            # En caso de error, retornar imagen original
            return imagen_path, {"error": str(e), "used": False}