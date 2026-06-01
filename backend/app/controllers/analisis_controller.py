"""
analisis_controller.py  — v6.0
Adaptado para arquitectura distribuida (Render ↔ Hugging Face Spaces).

CAMBIOS respecto a v5:
  - EstimacionService.estimar() devuelve (peso, bcs, confianza_pct, bcs_conf)
    igual que antes. Render no sabe ni le importa cómo HF calculó eso.
  - La morfometría REAL ahora viene del JSON de HF.
    Para acceder a ella, EstimacionService._ultima_morfometria se llena
    como efecto secundario de la llamada a estimar().
  - VisionService es un stub: solo decodifica, no corre SAM.
  - El resto del flujo (guardar en DB, responder al frontend) es IDÉNTICO a v5.
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
from app.schemas.schemas import AnalisisResultado, MedicionResponse, MorfometriaData
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

    # 2. Validar formato y tamaño
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

    # 3. Guardar imágenes en disco (para historial)
    medicion_id  = uuid.uuid4()
    url_lateral  = await _guardar_imagen(bytes_lateral, medicion_id, "lateral", imagen_lateral.content_type)
    url_trasera  = await _guardar_imagen(bytes_trasera, medicion_id, "trasera", imagen_trasera.content_type)

    ext_trasera  = imagen_trasera.content_type.split("/")[-1].replace("jpeg", "jpg")
    ruta_trasera = str(Path(settings.UPLOAD_DIR) / str(medicion_id) / f"trasera.{ext_trasera}")

    # 4. VisionService v6 stub — solo decodifica, no corre SAM
    #    La morfometría real vendrá del JSON de HF en el paso 5
    morfo_stub, img_lat, _ = await vision_service.analizar_imagenes(
        bytes_lateral, bytes_trasera
    )

    # 5. EstimacionService v6 — cliente HTTP hacia HF Spaces
    #    Envía ambas imágenes a HF y recibe peso + BCS + confianza
    peso_kg, bcs_final, confianza_pct, bcs_conf = estimacion_service.estimar(
        morfo_stub,
        imagen_lateral=img_lat,
        imagen_trasera=ruta_trasera,
    )

    # 6. Recuperar la morfometría REAL que devolvió HF
    #    EstimacionService la guarda en _ultima_morfometria tras cada llamada
    morfometria_real = getattr(estimacion_service, "_ultima_morfometria", None) or morfo_stub

    # 7. Confianza combinada
    confianza_vision = getattr(estimacion_service, "_ultima_confianza_vision", 1.0)
    confianza_final  = round((confianza_vision * 0.6) + (bcs_conf * 0.4), 3)

    # 8. Guardar en base de datos
    medicion = Medicion(
        id               = medicion_id,
        animal_id        = animal_id,
        peso_estimado_kg = peso_kg,
        bcs              = bcs_final,
        confianza        = confianza_pct,
        img_lateral_url  = url_lateral,
        img_trasera_url  = url_trasera,
        morfometria      = morfometria_real.model_dump()
                           if hasattr(morfometria_real, "model_dump")
                           else dict(morfometria_real),
        modelo_version   = estimacion_service.version,
        procesado_por    = "hf-spaces:mobilesam+cnn+yolo+xgboost",
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
        morfometria           = morfometria_real,
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