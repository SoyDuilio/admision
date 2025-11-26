from app.models.aula import Aula
from app.models.calificacion import Calificacion
from app.models.clave_respuesta import ClaveRespuesta
from app.models.hoja_respuesta import HojaRespuesta
from app.models.postulante import Postulante
from app.models.profesor import Profesor
from app.models.respuesta import Respuesta

# NUEVOS MODELOS:
from app.models.postulante_asignacion import PostulanteAsignacion
from app.models.asignacion_examen import AsignacionExamen
from app.models.venta_carpeta import VentaCarpeta
from app.models.verificacion_certificado import VerificacionCertificado
from app.models.log_anulacion import LogAnulacionHoja

__all__ = [
    "Aula",
    "Calificacion",
    "ClaveRespuesta",
    "HojaRespuesta",
    "Postulante",
    "Profesor",
    "Respuesta",
    "PostulanteAsignacion",
    "AsignacionExamen",  # ← AGREGAR
    "VentaCarpeta",
    "VerificacionCertificado",
    "LogAnulacionHoja"
]