"""
POSTULANDO - Servicio de Calificación
app/services/calificacion.py

Lógica de negocio para:
- Calificar hojas individuales
- Calificar todas las hojas de un proceso
- Generar estadísticas
- Comparar respuestas con gabarito
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from datetime import datetime
import time


class CalificacionService:
    """Servicio para calificación de hojas de respuesta"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calificar_hoja(self, hoja_id: int, proceso: str) -> Dict:
        """
        Califica una hoja de respuesta individual.
        
        Compara las respuestas del postulante con el gabarito
        y actualiza los campos correspondientes.
        
        Args:
            hoja_id: ID de la hoja de respuesta
            proceso: Código del proceso de admisión
            
        Returns:
            Diccionario con resultados de la calificación
        """
        
        # Obtener gabarito
        gabarito = self._obtener_gabarito(proceso)
        if not gabarito:
            raise ValueError(f"No existe gabarito para el proceso {proceso}")
        
        if len(gabarito) != 100:
            raise ValueError(f"Gabarito incompleto: {len(gabarito)} respuestas (se requieren 100)")
        
        # Obtener respuestas del postulante
        respuestas = self.db.execute(text("""
            SELECT id, numero_pregunta, respuesta_marcada
            FROM respuestas
            WHERE hoja_respuesta_id = :hoja_id
            ORDER BY numero_pregunta
        """), {"hoja_id": hoja_id}).fetchall()
        
        if not respuestas:
            raise ValueError(f"No hay respuestas para la hoja {hoja_id}")
        
        # Comparar y calificar
        correctas = 0
        incorrectas = 0
        en_blanco = 0
        
        for resp in respuestas:
            respuesta_correcta = gabarito.get(resp.numero_pregunta)
            respuesta_marcada = (resp.respuesta_marcada or "").strip().upper()
            
            if not respuesta_marcada:
                # En blanco
                es_correcta = False
                en_blanco += 1
            elif respuesta_marcada == respuesta_correcta:
                # Correcta
                es_correcta = True
                correctas += 1
            else:
                # Incorrecta
                es_correcta = False
                incorrectas += 1
            
            # Actualizar el campo es_correcta en la tabla respuestas
            self.db.execute(text("""
                UPDATE respuestas
                SET es_correcta = :es_correcta
                WHERE id = :id
            """), {"es_correcta": es_correcta, "id": resp.id})
        
        # Calcular nota (fórmula: +1 por correcta, 0 por incorrecta/blanco)
        nota_final = float(correctas)
        
        # Actualizar hoja de respuesta
        self.db.execute(text("""
            UPDATE hojas_respuestas
            SET 
                respuestas_correctas_count = :correctas,
                nota_final = :nota,
                fecha_calificacion = NOW(),
                updated_at = NOW()
            WHERE id = :hoja_id
        """), {
            "correctas": correctas,
            "nota": nota_final,
            "hoja_id": hoja_id
        })
        
        return {
            "hoja_id": hoja_id,
            "correctas": correctas,
            "incorrectas": incorrectas,
            "en_blanco": en_blanco,
            "nota_final": nota_final
        }
    
    def calificar_todas_las_hojas(self, proceso: str) -> Dict:
        """
        Califica todas las hojas de respuesta de un proceso.
        
        Args:
            proceso: Código del proceso de admisión
            
        Returns:
            Diccionario con resumen de la calificación
        """
        
        inicio = time.time()
        
        # Verificar gabarito
        gabarito = self._obtener_gabarito(proceso)
        if not gabarito or len(gabarito) != 100:
            raise ValueError(f"No existe gabarito completo para el proceso {proceso}")
        
        # Obtener todas las hojas procesadas
        hojas = self.db.execute(text("""
            SELECT id
            FROM hojas_respuestas
            WHERE proceso_admision = :proceso
            AND estado IN ('completado', 'calificado')
        """), {"proceso": proceso}).fetchall()
        
        if not hojas:
            raise ValueError(f"No hay hojas procesadas para el proceso {proceso}")
        
        # Calificar cada hoja
        total_hojas = 0
        suma_notas = 0
        nota_maxima = 0
        nota_minima = 100
        errores = []
        
        for hoja in hojas:
            try:
                resultado = self.calificar_hoja(hoja.id, proceso)
                total_hojas += 1
                suma_notas += resultado["nota_final"]
                
                if resultado["nota_final"] > nota_maxima:
                    nota_maxima = resultado["nota_final"]
                if resultado["nota_final"] < nota_minima:
                    nota_minima = resultado["nota_final"]
                    
            except Exception as e:
                errores.append({"hoja_id": hoja.id, "error": str(e)})
        
        # Commit de todos los cambios
        self.db.commit()
        
        fin = time.time()
        tiempo_segundos = fin - inicio
        
        promedio = suma_notas / total_hojas if total_hojas > 0 else 0
        
        return {
            "total_hojas": total_hojas,
            "hojas_con_error": len(errores),
            "errores": errores if errores else None,
            "promedio_nota": round(promedio, 2),
            "nota_maxima": nota_maxima,
            "nota_minima": nota_minima if total_hojas > 0 else 0,
            "tiempo_segundos": round(tiempo_segundos, 2)
        }
    
    def recalificar_hoja(self, hoja_id: int, proceso: str) -> Dict:
        """
        Recalifica una hoja específica (por si hubo correcciones).
        
        Args:
            hoja_id: ID de la hoja
            proceso: Código del proceso
            
        Returns:
            Resultado de la calificación
        """
        resultado = self.calificar_hoja(hoja_id, proceso)
        self.db.commit()
        return resultado
    
    def obtener_detalle_calificacion(self, hoja_id: int, proceso: str) -> Dict:
        """
        Obtiene el detalle completo de la calificación de una hoja.
        
        Incluye cada pregunta, la respuesta del postulante,
        la respuesta correcta y si acertó o no.
        
        Args:
            hoja_id: ID de la hoja
            proceso: Código del proceso
            
        Returns:
            Detalle completo de la calificación
        """
        
        # Obtener gabarito
        gabarito = self._obtener_gabarito(proceso)
        
        # Obtener respuestas con detalle
        respuestas = self.db.execute(text("""
            SELECT 
                r.numero_pregunta,
                r.respuesta_marcada,
                r.es_correcta,
                r.confianza,
                r.observacion
            FROM respuestas r
            WHERE r.hoja_respuesta_id = :hoja_id
            ORDER BY r.numero_pregunta
        """), {"hoja_id": hoja_id}).fetchall()
        
        # Obtener info de la hoja
        hoja = self.db.execute(text("""
            SELECT 
                hr.nota_final,
                hr.respuestas_correctas_count,
                hr.fecha_calificacion,
                p.dni,
                p.nombres,
                p.apellido_paterno,
                p.apellido_materno,
                p.programa_educativo
            FROM hojas_respuestas hr
            JOIN postulantes p ON p.id = hr.postulante_id
            WHERE hr.id = :hoja_id
        """), {"hoja_id": hoja_id}).fetchone()
        
        detalle_respuestas = []
        for r in respuestas:
            detalle_respuestas.append({
                "numero": r.numero_pregunta,
                "respuesta_postulante": r.respuesta_marcada or "-",
                "respuesta_correcta": gabarito.get(r.numero_pregunta, "-"),
                "es_correcta": r.es_correcta,
                "confianza": r.confianza,
                "observacion": r.observacion
            })
        
        return {
            "hoja_id": hoja_id,
            "postulante": {
                "dni": hoja.dni,
                "nombre_completo": f"{hoja.apellido_paterno} {hoja.apellido_materno}, {hoja.nombres}",
                "programa": hoja.programa_educativo
            },
            "nota_final": hoja.nota_final,
            "respuestas_correctas": hoja.respuestas_correctas_count,
            "fecha_calificacion": hoja.fecha_calificacion.isoformat() if hoja.fecha_calificacion else None,
            "detalle": detalle_respuestas
        }
    
    def obtener_estadisticas_proceso(self, proceso: str) -> Dict:
        """
        Obtiene estadísticas completas del proceso de calificación.
        
        Args:
            proceso: Código del proceso
            
        Returns:
            Estadísticas completas
        """
        
        # Estadísticas generales
        general = self.db.execute(text("""
            SELECT 
                COUNT(*) as total_hojas,
                COUNT(CASE WHEN nota_final IS NOT NULL THEN 1 END) as calificadas,
                AVG(nota_final) as promedio,
                MAX(nota_final) as maxima,
                MIN(nota_final) as minima,
                STDDEV(nota_final) as desviacion,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY nota_final) as mediana,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY nota_final) as percentil_25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY nota_final) as percentil_75
            FROM hojas_respuestas
            WHERE proceso_admision = :proceso
        """), {"proceso": proceso}).fetchone()
        
        # Distribución por rangos
        distribucion = self.db.execute(text("""
            SELECT 
                COUNT(CASE WHEN nota_final >= 90 THEN 1 END) as rango_90_100,
                COUNT(CASE WHEN nota_final >= 80 AND nota_final < 90 THEN 1 END) as rango_80_89,
                COUNT(CASE WHEN nota_final >= 70 AND nota_final < 80 THEN 1 END) as rango_70_79,
                COUNT(CASE WHEN nota_final >= 60 AND nota_final < 70 THEN 1 END) as rango_60_69,
                COUNT(CASE WHEN nota_final >= 50 AND nota_final < 60 THEN 1 END) as rango_50_59,
                COUNT(CASE WHEN nota_final < 50 THEN 1 END) as rango_menos_50
            FROM hojas_respuestas
            WHERE proceso_admision = :proceso AND nota_final IS NOT NULL
        """), {"proceso": proceso}).fetchone()
        
        # Estadísticas por programa
        por_programa = self.db.execute(text("""
            SELECT 
                p.programa_educativo,
                COUNT(*) as total,
                AVG(hr.nota_final) as promedio,
                MAX(hr.nota_final) as maxima,
                MIN(hr.nota_final) as minima
            FROM hojas_respuestas hr
            JOIN postulantes p ON p.id = hr.postulante_id
            WHERE hr.proceso_admision = :proceso AND hr.nota_final IS NOT NULL
            GROUP BY p.programa_educativo
            ORDER BY promedio DESC
        """), {"proceso": proceso}).fetchall()
        
        return {
            "proceso": proceso,
            "general": {
                "total_hojas": general.total_hojas,
                "calificadas": general.calificadas,
                "promedio": round(general.promedio, 2) if general.promedio else 0,
                "maxima": general.maxima or 0,
                "minima": general.minima or 0,
                "desviacion": round(general.desviacion, 2) if general.desviacion else 0,
                "mediana": round(general.mediana, 2) if general.mediana else 0,
                "percentil_25": round(general.percentil_25, 2) if general.percentil_25 else 0,
                "percentil_75": round(general.percentil_75, 2) if general.percentil_75 else 0
            },
            "distribucion": {
                "90-100": distribucion.rango_90_100 or 0,
                "80-89": distribucion.rango_80_89 or 0,
                "70-79": distribucion.rango_70_79 or 0,
                "60-69": distribucion.rango_60_69 or 0,
                "50-59": distribucion.rango_50_59 or 0,
                "<50": distribucion.rango_menos_50 or 0
            },
            "por_programa": [
                {
                    "programa": r.programa_educativo,
                    "total": r.total,
                    "promedio": round(r.promedio, 2) if r.promedio else 0,
                    "maxima": r.maxima or 0,
                    "minima": r.minima or 0
                }
                for r in por_programa
            ]
        }
    
    def analisis_preguntas(self, proceso: str) -> List[Dict]:
        """
        Analiza la dificultad de cada pregunta.
        
        Args:
            proceso: Código del proceso
            
        Returns:
            Lista con análisis de cada pregunta
        """
        
        result = self.db.execute(text("""
            SELECT 
                r.numero_pregunta,
                cr.respuesta_correcta,
                COUNT(*) as total_respuestas,
                COUNT(CASE WHEN r.respuesta_marcada = 'A' THEN 1 END) as marcaron_a,
                COUNT(CASE WHEN r.respuesta_marcada = 'B' THEN 1 END) as marcaron_b,
                COUNT(CASE WHEN r.respuesta_marcada = 'C' THEN 1 END) as marcaron_c,
                COUNT(CASE WHEN r.respuesta_marcada = 'D' THEN 1 END) as marcaron_d,
                COUNT(CASE WHEN r.respuesta_marcada = 'E' THEN 1 END) as marcaron_e,
                COUNT(CASE WHEN r.respuesta_marcada IS NULL OR r.respuesta_marcada = '' THEN 1 END) as en_blanco,
                COUNT(CASE WHEN r.es_correcta = TRUE THEN 1 END) as acertaron,
                ROUND(COUNT(CASE WHEN r.es_correcta = TRUE THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) as porcentaje_acierto
            FROM respuestas r
            JOIN hojas_respuestas hr ON hr.id = r.hoja_respuesta_id
            LEFT JOIN clave_respuestas cr ON cr.numero_pregunta = r.numero_pregunta 
                                           AND cr.proceso_admision = :proceso
            WHERE hr.proceso_admision = :proceso
            GROUP BY r.numero_pregunta, cr.respuesta_correcta
            ORDER BY r.numero_pregunta
        """), {"proceso": proceso}).fetchall()
        
        return [
            {
                "numero": r.numero_pregunta,
                "respuesta_correcta": r.respuesta_correcta,
                "total_respuestas": r.total_respuestas,
                "distribucion": {
                    "A": r.marcaron_a,
                    "B": r.marcaron_b,
                    "C": r.marcaron_c,
                    "D": r.marcaron_d,
                    "E": r.marcaron_e,
                    "Blanco": r.en_blanco
                },
                "acertaron": r.acertaron,
                "porcentaje_acierto": float(r.porcentaje_acierto) if r.porcentaje_acierto else 0,
                "dificultad": self._clasificar_dificultad(r.porcentaje_acierto)
            }
            for r in result
        ]
    
    def _obtener_gabarito(self, proceso: str) -> Dict[int, str]:
        """
        Obtiene el gabarito como diccionario {numero_pregunta: respuesta_correcta}
        """
        result = self.db.execute(text("""
            SELECT numero_pregunta, respuesta_correcta
            FROM clave_respuestas
            WHERE proceso_admision = :proceso
            ORDER BY numero_pregunta
        """), {"proceso": proceso}).fetchall()
        
        return {r.numero_pregunta: r.respuesta_correcta.upper() for r in result}
    
    def _clasificar_dificultad(self, porcentaje: float) -> str:
        """Clasifica la dificultad de una pregunta según el porcentaje de acierto"""
        if porcentaje is None:
            return "Sin datos"
        if porcentaje >= 80:
            return "Muy fácil"
        elif porcentaje >= 60:
            return "Fácil"
        elif porcentaje >= 40:
            return "Media"
        elif porcentaje >= 20:
            return "Difícil"
        else:
            return "Muy difícil"