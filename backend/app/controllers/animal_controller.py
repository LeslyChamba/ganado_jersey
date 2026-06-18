import uuid
import time
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Animal, Hato, Medicion, Usuario
from app.schemas.schemas import AnalisisResultado, MedicionResponse, ValidacionFotoOut, ValidacionParOut
from app.services.vision_service import vision_service
from app.services.estimacion_service import estimacion_service
from app.services.validacion_service import validacion_service
from app.controllers.auth_controller import get_current_user
from app.core.config import settings

# Definición estándar del router para que main.py lo importe correctamente
router = APIRouter(prefix="/analisis", tags=["Análisis de Imágenes"])
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.post(
    "/validar",
    response_model=ValidacionParOut,
    status_code=status.HTTP_200_OK,
    summary="Valida si las fotos son aptas antes del análisis completo",
    description=(
        "Corre únicamente YOLOv8 detección (sin SAM ni CNN) para verificar "
        "que ambas imágenes contienen un bovino correctamente posicionado. "
        "Devuelve feedback específico por foto. Llamar ANTES de POST /analisis/."
    ),
)
async def validar_imagenes(
    imagen_lateral: UploadFile = File(..., description="Foto de perfil lateral de la vaca"),
    imagen_trasera: UploadFile = File(..., description="Foto posterior (grupa) de la vaca"),
    current_user:   Usuario    = Depends(get_current_user),
):
    for img, nombre in [(imagen_lateral, "lateral"), (imagen_trasera, "trasera")]:
        if img.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: formato '{img.content_type}' no soportado. "
                       f"Usa JPEG, PNG o WebP."
            )
        if img.size and img.size > settings.MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: supera el tamaño máximo permitido."
            )

    bytes_lateral = await imagen_lateral.read()
    bytes_trasera = await imagen_trasera.read()

    resultado = await validacion_service.validar_par(bytes_lateral, bytes_trasera)

    return ValidacionParOut(
        lateral=ValidacionFotoOut(**vars(resultado.lateral)),
        trasera=ValidacionFotoOut(**vars(resultado.trasera)),
        par_valido=resultado.par_valido,
    )


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

    # 1. Verificar animal
    animal = db.query(Animal).join(Hato).filter(
        Animal.id == animal_id,
        Hato.propietario_id == current_user.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")

    # 2. Validar imágenes
    for img, nombre in [(imagen_lateral, "lateral"), (imagen_trasera, "trasera")]:
        if img.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: formato no soportado."
            )
        if img.size and img.size > settings.MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: demasiado grande."
            )

    bytes_lateral = await imagen_lateral.read()
    bytes_trasera = await imagen_trasera.read()

    # 3. Guardar imágenes
    medicion_id  = uuid.uuid4()
    url_lateral  = await _guardar_imagen(bytes_lateral, medicion_id, "lateral", imagen_lateral.content_type)
    url_trasera  = await _guardar_imagen(bytes_trasera, medicion_id, "trasera", imagen_trasera.content_type)

    ext_trasera  = imagen_trasera.content_type.split("/")[-1].replace("jpeg", "jpg")
    ruta_trasera = str(
        Path(settings.UPLOAD_DIR) / str(medicion_id) / f"trasera.{ext_trasera}"
    )

    # ── 4. Pipeline visión — SAM + BCS ────────────────────────────────────
    morfometria, img_lat, confianza_vision, bcs, bcs_conf = \
        await vision_service.analizar_imagenes(bytes_lateral, bytes_trasera)

    # ── 5. Estimación de peso — CNN híbrido (principal) + XGBoost (respaldo)
    peso_kg, bcs_final, confianza_ml, confianza_bcs = estimacion_service.estimar(
        morfometria,
        imagen_lateral=img_lat,       # ← ndarray BGR para CNN híbrido
        imagen_trasera=ruta_trasera,  # ← path para YOLO BCS
    )

    confianza_final = round((confianza_vision * 0.6) + (confianza_bcs * 0.4), 3)

    # ── 6. Guardar en BD ───────────────────────────────────────────────────
    medicion = Medicion(
        id               = medicion_id,
        animal_id        = animal_id,
        peso_estimado_kg = peso_kg,
        bcs              = bcs_final,
        confianza        = confianza_final * 100,
        img_lateral_url  = url_lateral,
        img_trasera_url  = url_trasera,
        morfometria      = morfometria.model_dump(),
        modelo_version   = estimacion_service.version,
        procesado_por    = "sam+yolo+cnn_hibrido",
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
        confianza_peso        = round(confianza_ml, 1),
        confianza_bcs         = round(confianza_bcs * 100, 1),
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
        Hato.propietario_id == current_user.id
    ).first()
    if not medicion:
        raise HTTPException(status_code=404, detail="Medición no encontrada")
    return MedicionResponse.model_validate(medicion)


async def _guardar_imagen(imagen_bytes, medicion_id, vista, content_type):
    ext        = content_type.split("/")[-1].replace("jpeg", "jpg")
    directorio = Path(settings.UPLOAD_DIR) / str(medicion_id)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta       = directorio / f"{vista}.{ext}"
    async with aiofiles.open(ruta, "wb") as f:
        await f.write(imagen_bytes)
    return f"/uploads/{medicion_id}/{vista}.{ext}"