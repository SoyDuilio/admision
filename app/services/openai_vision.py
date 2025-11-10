import os
import base64
from typing import List, Optional

# Intentar importar OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI no instalado. Ejecuta: pip install openai")


class OpenAIVisionService:
    """
    Servicio para procesar imágenes con OpenAI GPT-4 Vision API
    """
    
    def __init__(self):
        self.client = None
        self.available = False
        
        if not OPENAI_AVAILABLE:
            print("❌ OpenAI SDK no está instalado")
            return
        
        # Obtener API key del entorno
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            print("⚠️  OPENAI_API_KEY no configurado en .env")
            return
        
        try:
            self.client = OpenAI(api_key=api_key)
            self.available = True
            print("✅ OpenAI Vision inicializado correctamente")
        except Exception as e:
            print(f"❌ Error inicializando OpenAI: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.available and self.client is not None
    
    async def extraer_respuestas(self, imagen_bytes: bytes) -> List[dict]:
        """
        Extrae respuestas de una hoja de respuestas usando GPT-4 Vision
        
        Args:
            imagen_bytes: Bytes de la imagen a procesar
            
        Returns:
            List[dict]: Lista de respuestas detectadas
            [
                {"numero_pregunta": 1, "respuesta_detectada": "a", "confianza": 95.5},
                ...
            ]
        """
        if not self.is_available():
            raise Exception(
                "OpenAI Vision no está disponible. "
                "Verifica OPENAI_API_KEY en tu archivo .env"
            )
        
        try:
            # Convertir bytes a base64
            base64_image = base64.b64encode(imagen_bytes).decode('utf-8')
            
            # Crear el prompt para GPT-4 Vision
            prompt = """
Analiza esta hoja de respuestas de examen de admisión.

La hoja contiene 100 preguntas numeradas del 1 al 100.
Cada pregunta tiene 5 alternativas: a, b, c, d, e.
El postulante debe haber marcado UNA sola alternativa por pregunta.

Tu tarea:
1. Identifica qué alternativa está marcada para cada pregunta (1-100)
2. Si una pregunta no tiene respuesta o es ilegible, indica null
3. Devuelve SOLO un objeto JSON con este formato exacto:

{
  "respuestas": [
    {"pregunta": 1, "respuesta": "a"},
    {"pregunta": 2, "respuesta": "b"},
    ...
    {"pregunta": 100, "respuesta": "e"}
  ]
}

IMPORTANTE: 
- Devuelve SOLO el JSON, sin texto adicional
- Todas las 100 preguntas deben estar en el array
- Las respuestas deben ser: "a", "b", "c", "d", "e" o null
"""
            
            # Llamar a GPT-4 Vision
            response = self.client.chat.completions.create(
                model="gpt-4o",  # o "gpt-4-vision-preview"
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1
            )
            
            # Extraer el contenido de la respuesta
            contenido = response.choices[0].message.content
            print(f"📄 Respuesta de OpenAI recibida ({len(contenido)} caracteres)")
            
            # Parsear la respuesta
            respuestas = self._parsear_respuesta_gpt(contenido)
            
            return respuestas
            
        except Exception as e:
            print(f"❌ Error en OpenAI Vision: {e}")
            raise
    
    def _parsear_respuesta_gpt(self, contenido: str) -> List[dict]:
        """
        Parsea la respuesta JSON de GPT-4 Vision
        
        Args:
            contenido: Respuesta de GPT-4 (debe ser JSON)
            
        Returns:
            Lista de respuestas estandarizada
        """
        import json
        import re
        
        try:
            # Limpiar el contenido por si tiene markdown
            contenido_limpio = contenido.strip()
            
            # Remover bloques de código markdown si existen
            contenido_limpio = re.sub(r'```json\s*', '', contenido_limpio)
            contenido_limpio = re.sub(r'```\s*$', '', contenido_limpio)
            
            # Parsear JSON
            data = json.loads(contenido_limpio)
            
            # Convertir al formato estandarizado
            respuestas = []
            for item in data.get('respuestas', []):
                respuestas.append({
                    "numero_pregunta": item['pregunta'],
                    "respuesta_detectada": item['respuesta'],
                    "confianza": 90.0  # GPT-4 no devuelve confianza, usamos valor fijo alto
                })
            
            # Verificar que tengamos 100 respuestas
            if len(respuestas) != 100:
                print(f"⚠️  Se esperaban 100 respuestas, se obtuvieron {len(respuestas)}")
            
            return respuestas
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON de OpenAI: {e}")
            print(f"Contenido recibido: {contenido[:500]}...")
            raise Exception("OpenAI no devolvió un JSON válido")
        except Exception as e:
            print(f"❌ Error procesando respuesta de OpenAI: {e}")
            raise


# ===== SINGLETON =====
openai_vision_service = OpenAIVisionService()


# ===== FUNCIÓN DE TEST =====
def test_openai_vision():
    """Función para probar si OpenAI Vision está configurado"""
    print("\n" + "="*50)
    print("🧪 TEST: OpenAI Vision Service")
    print("="*50)
    
    service = OpenAIVisionService()
    
    print(f"\n📊 Estado:")
    print(f"  - Módulo instalado: {OPENAI_AVAILABLE}")
    print(f"  - Servicio disponible: {service.is_available()}")
    print(f"  - Cliente inicializado: {service.client is not None}")
    
    print(f"\n🔧 Variables de entorno:")
    api_key = os.getenv('OPENAI_API_KEY', '')
    if api_key:
        print(f"  - OPENAI_API_KEY: {api_key[:10]}...{api_key[-4:]}")
    else:
        print(f"  - OPENAI_API_KEY: No configurado")
    
    print("\n" + "="*50 + "\n")
    
    return service.is_available()


if __name__ == "__main__":
    test_openai_vision()