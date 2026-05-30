"""
analisis_controller.py  — v5.0
Adaptado para VisionService v5 (retorna 3 valores: morfo, img_lat, confianza_vision).
EstimacionService v5 retorna 4 valores: (peso, bcs, confianza_pct, bcs_conf).
analisis_controller pasa img_lat directamente a estimar() para la CNN híbrida.
"""
import uuid
import time
import aiofiles
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Animal, Hato, Medicion, Usuario
from app.schemas.schemas import AnalisisResultado, MedicionResponse
from app.services.vision_service import vision_service
from app.services.estimacion_service import estimacion_service
from app.controllers.auth_controller import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/analisis", tags=["Análisis de Imágenes"])
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.post("/", response_model=AnalisisResultado, status_code=status.HTTP_201_CREATED)
async def analizar_vaca(
    animal_id:      uuid.UUID     = Form(...),
    imagen_lateral: UploadFile    = File(...),
    imagen_trasera: UploadFile    = File(...),
    notas:          Optional[str] = Form(None),
    db:             Session       = Depends(get_db),
    current_user:   Usuario       = Depends(get_current_user),
):
    inicio = time.time()

    # 1. Verificar que el animal pertenece al usuario
    animal = db.query(Animal).join(Hato).filter(
        Animal.id == animal_id,
        Hato.propietario_id == current_user.id,
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")

    # 2. Validar formato y tamaño de imágenes
    for img, nombre in [(imagen_lateral, "lateral"), (imagen_trasera, "trasera")]:
        if img.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: formato no soportado. Use JPG, PNG o WEBP.",
            )
        if img.size and img.size > settings.MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: demasiado grande (máx {settings.MAX_IMAGE_SIZE_BYTES // 1024 // 1024} MB).",
            )

    bytes_lateral = await imagen_lateral.read()
    bytes_trasera = await imagen_trasera.read()

    # 3. Guardar imágenes en disco
    medicion_id  = uuid.uuid4()
    url_lateral  = await _guardar_imagen(bytes_lateral, medicion_id, "lateral", imagen_lateral.content_type)
    url_trasera  = await _guardar_imagen(bytes_trasera, medicion_id, "trasera", imagen_trasera.content_type)

    ext_trasera  = imagen_trasera.content_type.split("/")[-1].replace("jpeg", "jpg")
    ruta_trasera = str(Path(settings.UPLOAD_DIR) / str(medicion_id) / f"trasera.{ext_trasera}")

    # 4. VisionService v5 — MobileSAM + morfometría (retorna 3 valores)
    morfometria, img_lat, confianza_vision = await vision_service.analizar_imagenes(
        bytes_lateral, bytes_trasera
    )

    # 5. EstimacionService v5 — CNN híbrida + BCS YOLO (retorna 4 valores)
    #    img_lat se pasa para la CNN; ruta_trasera para YOLO BCS
    peso_kg, bcs_final, confianza_pct, bcs_conf = estimacion_service.estimar(
        morfometria,
        imagen_lateral=img_lat,
        imagen_trasera=ruta_trasera,
    )

    # 6. Confianza combinada: 60 % morfometría SAM + 40 % BCS YOLO
    confianza_final = round((confianza_vision * 0.6) + (bcs_conf * 0.4), 3)

    # 7. Guardar en base de datos
    medicion = Medicion(
        id               = medicion_id,
        animal_id        = animal_id,
        peso_estimado_kg = peso_kg,
        bcs              = bcs_final,
        confianza        = confianza_pct,
        img_lateral_url  = url_lateral,
        img_trasera_url  = url_trasera,
        morfometria      = morfometria.model_dump(),
        modelo_version   = estimacion_service.version,
        procesado_por    = "mobilesam+cnn_hibrido+yolo+xgboost",
        notas            = notas,
    )
    db.add(medicion)
    db.commit()
    db.refresh(medicion)

    interpretacion, recomendacion = estimacion_service.interpretar_bcs(bcs_final)

    return AnalisisResultado(
        peso_estimado_kg      = peso_kg,
        bcs                   = bcs_final,
        confianza             = round(confianza_final * 100, 1),
        interpretacion_bcs    = interpretacion,
        recomendacion         = recomendacion,
        morfometria           = morfometria,
        medicion_id           = medicion_id,
        procesado_en_segundos = round(time.time() - inicio, 2),
    )


@router.get("/medicion/{medicion_id}", response_model=MedicionResponse)
def obtener_medicion(
    medicion_id:  uuid.UUID,
    db:           Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    medicion = db.query(Medicion).join(Animal).join(Hato).filter(
        Medicion.id == medicion_id,
        Hato.propietario_id == current_user.id,
    ).first()
    if not medicion:
        raise HTTPException(status_code=404, detail="Medición no encontrada")
    return MedicionResponse.model_validate(medicion)


async def _guardar_imagen(imagen_bytes: bytes, medicion_id: uuid.UUID, vista: str, content_type: str) -> str:
    ext        = content_type.split("/")[-1].replace("jpeg", "jpg")
    directorio = Path(settings.UPLOAD_DIR) / str(medicion_id)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / f"{vista}.{ext}"
    async with aiofiles.open(ruta, "wb") as f:
        await f.write(imagen_bytes)
    return f"/uploads/{medicion_id}/{vista}.{ext}"