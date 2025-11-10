import os
import json
from typing import List, Optional
from PIL import Image
import io

# Intentar importar Google Vision
try:
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    print("⚠️  Google Cloud Vision no instalado. Ejecuta: pip install google-cloud-vision")


class GoogleVisionService:
    """
    Servicio para procesar imágenes con Google Cloud Vision API
    Soporta dos modos:
    - Local: GOOGLE_APPLICATION_CREDENTIALS (archivo JSON)
    - Railway: GOOGLE_CREDENTIALS_JSON (variable de entorno con JSON completo)
    """
    
    def __init__(self):
        self.client = None
        self.available = False
        
        if not GOOGLE_VISION_AVAILABLE:
            print("❌ Google Cloud Vision no está instalado")
            return
        
        try:
            # ===== OPCIÓN 1: Desde archivo (desarrollo local) =====
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path):
                self.client = vision.ImageAnnotatorClient()
                self.available = True
                print(f"✅ Google Vision inicializado desde archivo: {credentials_path}")
                return
            
            # ===== OPCIÓN 2: Desde variable JSON (Railway) =====
            credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if credentials_json:
                try:
                    credentials_dict = json.loads(credentials_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict,
                        scopes=['https://www.googleapis.com/auth/cloud-vision']
                    )
                    self.client = vision.ImageAnnotatorClient(credentials=credentials)
                    self.available = True
                    print("✅ Google Vision inicializado desde variable de entorno JSON")
                    return
                except json.JSONDecodeError as e:
                    print(f"❌ Error parseando GOOGLE_CREDENTIALS_JSON: {e}")
                except Exception as e:
                    print(f"❌ Error creando credentials desde JSON: {e}")
            
            # Si llegamos aquí, no hay credenciales configuradas
            print("⚠️  Google Vision: No se encontraron credenciales")
            print("    Configura GOOGLE_APPLICATION_CREDENTIALS o GOOGLE_CREDENTIALS_JSON")
            
        except Exception as e:
            print(f"❌ Error inicializando Google Vision: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.available and self.client is not None
    
    async def extraer_respuestas(self, imagen_bytes: bytes) -> List[dict]:
        """
        Extrae respuestas de una hoja de respuestas usando Google Vision
        
        Args:
            imagen_bytes: Bytes de la imagen a procesar
            
        Returns:
            List[dict]: Lista de respuestas detectadas
            [
                {"numero_pregunta": 1, "respuesta_detectada": "a", "confianza": 95.5},
                {"numero_pregunta": 2, "respuesta_detectada": "b", "confianza": 98.2},
                ...
            ]
        """
        if not self.is_available():
            raise Exception(
                "Google Vision no está disponible. "
                "Verifica las credenciales en GOOGLE_APPLICATION_CREDENTIALS o GOOGLE_CREDENTIALS_JSON"
            )
        
        try:
            # Crear objeto Image de Google Vision
            image = vision.Image(content=imagen_bytes)
            
            # Ejecutar detección de texto
            response = self.client.text_detection(image=image)
            
            # Verificar errores de la API
            if response.error.message:
                raise Exception(f"Error de Google Vision API: {response.error.message}")
            
            texts = response.text_annotations
            
            if not texts:
                raise Exception("No se detectó texto en la imagen")
            
            # El primer elemento contiene todo el texto detectado
            texto_completo = texts[0].description
            print(f"📄 Texto detectado por Google Vision ({len(texto_completo)} caracteres)")
            
            # Parsear las respuestas del texto
            respuestas = self._parsear_respuestas(texto_completo)
            
            return respuestas
            
        except Exception as e:
            print(f"❌ Error en Google Vision: {e}")
            raise
    
    def _parsear_respuestas(self, texto: str) -> List[dict]:
        """
        Parsea el texto extraído para obtener las respuestas marcadas
        
        NOTA: Esta es una implementación simplificada para la demo.
        En producción, deberías usar un LLM (GPT-4 o Claude) para 
        interpretar el texto y extraer las respuestas con mayor precisión.
        
        Args:
            texto: Texto extraído de la imagen
            
        Returns:
            Lista de 100 respuestas con formato estandarizado
        """
        # TODO: Implementar parsing inteligente con LLM
        # Por ahora, generamos respuestas de ejemplo para testing
        
        print("⚠️  Usando parser simplificado. TODO: Implementar con LLM")
        
        respuestas = []
        
        # Ejemplo: generar 100 respuestas dummy
        # En producción, aquí irías línea por línea extrayendo las respuestas
        for i in range(1, 101):
            respuestas.append({
                "numero_pregunta": i,
                "respuesta_detectada": "a",  # Placeholder
                "confianza": 85.0
            })
        
        return respuestas
    
    def validar_imagen(self, imagen_bytes: bytes) -> bool:
        """
        Valida que la imagen sea válida y pueda procesarse
        
        Args:
            imagen_bytes: Bytes de la imagen
            
        Returns:
            bool: True si la imagen es válida
        """
        try:
            # Intentar abrir la imagen con Pillow
            img = Image.open(io.BytesIO(imagen_bytes))
            
            # Verificar dimensiones mínimas
            width, height = img.size
            if width < 800 or height < 1000:
                print(f"⚠️  Imagen muy pequeña: {width}x{height}")
                return False
            
            # Verificar formato
            if img.format not in ['JPEG', 'PNG', 'JPG']:
                print(f"⚠️  Formato no soportado: {img.format}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error validando imagen: {e}")
            return False


# ===== SINGLETON =====
google_vision_service = GoogleVisionService()


# ===== FUNCIÓN AUXILIAR PARA TESTING =====
def test_google_vision():
    """Función para probar si Google Vision está configurado correctamente"""
    print("\n" + "="*50)
    print("🧪 TEST: Google Vision Service")
    print("="*50)
    
    service = GoogleVisionService()
    
    print(f"\n📊 Estado:")
    print(f"  - Módulo instalado: {GOOGLE_VISION_AVAILABLE}")
    print(f"  - Servicio disponible: {service.is_available()}")
    print(f"  - Cliente inicializado: {service.client is not None}")
    
    print(f"\n🔧 Variables de entorno:")
    print(f"  - GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'No configurado')}")
    print(f"  - GOOGLE_CREDENTIALS_JSON: {'Configurado' if os.getenv('GOOGLE_CREDENTIALS_JSON') else 'No configurado'}")
    
    print("\n" + "="*50 + "\n")
    
    return service.is_available()


# Si ejecutas este archivo directamente, hace el test
if __name__ == "__main__":
    test_google_vision()