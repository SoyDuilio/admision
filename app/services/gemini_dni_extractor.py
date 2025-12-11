import os
from google import genai
from google.genai import types
from pathlib import Path

def extraer_dni_gemini_sdk(image_path: str) -> dict:
    """
    Extractor DNI usando el SDK oficial de Gemini.
    Usa el nuevo SDK 'google.genai' con mejor control.
    """
    try:
        client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        )
        
        # Schema con instrucciones detalladas
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "dni": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "El número de DNI de 8 dígitos escrito a mano. "
                        "CRÍTICO: Diferencia entre '4' (forma triangular cerrada) "
                        "y '7' (trazo horizontal superior con diagonal). "
                        "Si dos dígitos tienen la misma forma manuscrita, son el mismo número."
                    )
                ),
                "confianza": types.Schema(
                    type=types.Type.STRING,
                    description="'alta', 'media' o 'baja' según claridad de la escritura"
                )
            },
            required=["dni", "confianza"]
        )
        
        # Leer imagen
        with open(image_path, "rb") as f:
            imagen_bytes = f.read()
        
        # Llamada a Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(imagen_bytes, "image/jpeg"),
                "Extrae el DNI de 8 dígitos de esta imagen. Analiza cuidadosamente cada dígito."
            ],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=schema,
                temperature=0.0,
                system_instruction=(
                    "Eres un OCR especializado en dígitos manuscritos peruanos. "
                    "Tu prioridad es la precisión absoluta. "
                    "Si un dígito es ambiguo entre 4 y 7, usa el contexto de otros dígitos similares."
                )
            )
        )
        
        return {
            "success": True,
            "dni": response.parsed.get("dni", ""),
            "confianza": response.parsed.get("confianza", "media")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }