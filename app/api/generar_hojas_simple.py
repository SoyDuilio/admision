"""
API para generar hojas de respuestas genéricas
Versión actualizada: Genera para postulantes O genéricas
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime
from io import BytesIO
import tempfile
import zipfile
import os
import shutil
import secrets
import string

from app.database import get_db
from app.services.pdf_generator_simple import generar_hoja_generica

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class GenerarHojasRequest(BaseModel):
    proceso_admision: str = "2025-2"
    cantidad_hojas: int = 5
    descripcion: str = "Examen de Admisión"
    tipo_generacion: str = "generica"  # "generica" o "postulantes"


@router.get("/admin/generar-simple", response_class=HTMLResponse)
async def formulario_generar_simple(
    request: Request,
    db: Session = Depends(get_db)
):
    """Formulario para generar hojas"""
    
    # Contar postulantes por proceso
    query_count = text("""
        SELECT 
            proceso_admision,
            COUNT(*) as total
        FROM postulantes
        GROUP BY proceso_admision
        ORDER BY proceso_admision DESC
    """)
    
    procesos = db.execute(query_count).fetchall()
    
    # Crear dict con totales
    totales_por_proceso = {p.proceso_admision: p.total for p in procesos}
    
    return templates.TemplateResponse("admin/generar_simple.html", {
        "request": request,
        "totales_por_proceso": totales_por_proceso
    })


@router.post("/api/generar-hojas-genericas")
async def generar_hojas_genericas_api(
    data: GenerarHojasRequest,
    db: Session = Depends(get_db)
):
    """
    Genera hojas genéricas O para postulantes
    """
    
    proceso = data.proceso_admision
    cantidad = data.cantidad_hojas
    descripcion = data.descripcion
    tipo = data.tipo_generacion
    
    try:
        print(f"\n{'='*70}")
        print(f"📄 GENERANDO HOJAS - Tipo: {tipo.upper()}")
        print(f"{'='*70}\n")
        
        temp_dir = tempfile.mkdtemp()
        todos_los_pdfs = []
        
        # ================================================================
        # MODO 1: GENERAR PARA POSTULANTES
        # ================================================================
        
        if tipo == "postulantes":
            
            # Obtener postulantes
            query_postulantes = text("""
                SELECT 
                    p.id,
                    p.dni,
                    p.apellido_paterno,
                    p.apellido_materno,
                    p.nombres,
                    p.programa_educativo
                FROM postulantes p
                WHERE p.proceso_admision = :proceso
                ORDER BY p.apellido_paterno, p.apellido_materno, p.nombres
            """)
            
            postulantes = db.execute(query_postulantes, {"proceso": proceso}).fetchall()
            total = len(postulantes)
            
            if total == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay postulantes registrados en {proceso}"
                )
            
            print(f"✅ Postulantes encontrados: {total}\n")
            
            for i, p in enumerate(postulantes, 1):
                
                # Verificar si ya tiene hoja
                query_hoja = text("""
                    SELECT id, codigo_hoja 
                    FROM hojas_respuestas
                    WHERE postulante_id = :postulante_id
                      AND proceso_admision = :proceso
                    LIMIT 1
                """)
                
                hoja_existente = db.execute(query_hoja, {
                    "postulante_id": p.id,
                    "proceso": proceso
                }).fetchone()
                
                if hoja_existente:
                    codigo_hoja = hoja_existente.codigo_hoja
                    print(f"  {i}/{total}: {p.apellido_paterno} - Usando hoja existente: {codigo_hoja}")
                else:
                    # Generar código único
                    codigo_hoja = generar_codigo_unico(db)
                    
                    # Crear hoja en BD
                    query_insert = text("""
                        INSERT INTO hojas_respuestas (
                            postulante_id, codigo_hoja, proceso_admision,
                            estado, numero_hoja, created_at
                        ) VALUES (
                            :postulante_id, :codigo, :proceso,
                            'generada', :numero, NOW()
                        )
                        RETURNING id
                    """)
                    
                    db.execute(query_insert, {
                        "postulante_id": p.id,
                        "codigo": codigo_hoja,
                        "proceso": proceso,
                        "numero": i
                    })
                    db.commit()
                    
                    print(f"  {i}/{total}: {p.apellido_paterno} {p.apellido_materno}, {p.nombres} → {codigo_hoja}")
                
                # Generar PDF (SIN DNI preimpreso)
                filename = f"hoja_{i:03d}_{codigo_hoja}.pdf"
                filepath = os.path.join(temp_dir, filename)
                
                generar_hoja_generica(
                    output_path=filepath,
                    numero_hoja= i,
                    codigo_hoja=codigo_hoja,
                    proceso=proceso,
                    descripcion=descripcion
                )
                
                todos_los_pdfs.append(filepath)
        
        # ================================================================
        # MODO 2: GENERAR HOJAS GENÉRICAS (sin postulante)
        # ================================================================
        
        else:
            
            print(f"📝 Generando {cantidad} hojas genéricas\n")
            
            for i in range(1, cantidad + 1):
                
                # Generar código único
                codigo_hoja = generar_codigo_unico(db)
                
                # Crear hoja en BD (sin postulante)
                query_insert = text("""
                    INSERT INTO hojas_respuestas (
                        postulante_id, codigo_hoja, proceso_admision,
                        estado, numero_hoja, created_at
                    ) VALUES (
                        NULL, :codigo, :proceso, 'generada', :numero, NOW()
                    )
                    RETURNING id
                """)
                
                db.execute(query_insert, {
                    "codigo": codigo_hoja,
                    "proceso": proceso,
                    "numero": i
                })
                db.commit()
                
                print(f"  {i}/{cantidad}: {codigo_hoja}")
                
                # Generar PDF
                filename = f"hoja_{i:03d}_{codigo_hoja}.pdf"
                filepath = os.path.join(temp_dir, filename)
                
                generar_hoja_generica(
                    output_path=filepath,
                    numero_hoja=i,
                    codigo_hoja=codigo_hoja,
                    proceso=proceso,
                    descripcion=descripcion
                )
                
                todos_los_pdfs.append(filepath)
        
        # ================================================================
        # CREAR ZIP
        # ================================================================
        
        print(f"\n📦 Creando ZIP...")
        print(f"   Total archivos: {len(todos_los_pdfs)}\n")
        
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for pdf_file in todos_los_pdfs:
                if os.path.exists(pdf_file):
                    arcname = os.path.basename(pdf_file)
                    zip_file.write(pdf_file, arcname)
        
        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()
        zip_size = len(zip_bytes)
        
        # Limpiar temporales
        shutil.rmtree(temp_dir)
        
        # ================================================================
        # RESPUESTA
        # ================================================================
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tipo_nombre = "postulantes" if tipo == "postulantes" else "genericas"
        filename = f"hojas_{tipo_nombre}_{proceso}_{timestamp}.zip"
        
        print(f"{'='*70}")
        print(f"✅ GENERACIÓN COMPLETADA")
        print(f"{'='*70}")
        print(f"📦 ZIP: {zip_size / (1024*1024):.2f} MB")
        print(f"📝 Total hojas: {len(todos_los_pdfs)}")
        print(f"{'='*70}\n")
        
        return StreamingResponse(
            iter([zip_bytes]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(zip_size)
            }
        )
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def generar_codigo_unico(db: Session) -> str:
    """Genera código único: ABC12345D"""
    
    while True:
        # 3 letras + 5 dígitos + 1 letra
        letras1 = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(3))
        numeros = ''.join(secrets.choice(string.digits) for _ in range(5))
        letra2 = secrets.choice(string.ascii_uppercase)
        
        codigo = f"{letras1}{numeros}{letra2}"
        
        # Verificar unicidad
        query = text("""
            SELECT COUNT(*) FROM hojas_respuestas
            WHERE codigo_hoja = :codigo
        """)
        
        existe = db.execute(query, {"codigo": codigo}).scalar()
        
        if not existe:
            return codigo