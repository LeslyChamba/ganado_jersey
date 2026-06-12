"""
analisis_controller.py  — v6.0 (Estabilizado)
Adaptado para arquitectura distribuida (Render ↔ Hugging Face Spaces).

Flujo limpio libre de NameError y AttributeError:
  - Inicializa morfo_stub directamente desde el esquema de Pydantic.
  - Decodifica la imagen lateral a una matriz BGR compatible con la CNN.
  - Sifona las rutas de archivos guardados correctamente hacia el estimador.
  - Mapea las confianzas reales de la IA hacia el Frontend de React.
"""
import uuid
import time
import aiofiles
import cv2
import numpy as np
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

    # 1. Verificar que el animal pertenece al usuario autenticado
    animal = db.query(Animal).join(Hato).filter(
        Animal.id == animal_id,
        Hato.propietario_id == current_user.id,
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")

    # 2. Validar formato y restricciones de tamaño de archivos
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

    # Lectura asíncrona de los flujos de bytes
    bytes_lateral = await imagen_lateral.read()
    bytes_trasera = await imagen_trasera.read()

    # ── Tubería de Visión Stub (Instanciación segura libre de AttributeError) ──
    morfo_stub = MorfometriaData(
        largo_corporal_cm=0.0,
        alzada_cm=0.0,
        perimetro_toracico_cm=0.0,
        ancho_caderas_cm=0.0,
        profundidad_toracica_cm=0.0,
        longitud_grupa_cm=0.0
    )

    # 3. Almacenamiento local de imágenes para auditoría e historial
    medicion_id  = uuid.uuid4()
    url_lateral  = await _guardar_imagen(bytes_lateral, medicion_id, "lateral", imagen_lateral.content_type)
    url_trasera  = await _guardar_imagen(bytes_trasera, medicion_id, "trasera", imagen_trasera.content_type)

    ext_trasera  = imagen_trasera.content_type.split("/")[-1].replace("jpeg", "jpg")
    ruta_trasera = str(Path(settings.UPLOAD_DIR) / str(medicion_id) / f"trasera.{ext_trasera}")

    # ── Paso 4.5: Decodificación de la imagen de perfil a matriz BGR para OpenCV ──
    await imagen_lateral.seek(0)
    bytes_lateral_recomp = await imagen_lateral.read()
    nparr_lat = np.frombuffer(bytes_lateral_recomp, np.uint8)
    img_lateral_bgr = cv2.imdecode(nparr_lat, cv2.IMREAD_COLOR)

    # ── Paso 5: Ejecución del Motor de Inferencia Distribuido (Hugging Face) ──
    peso_kg, bcs_final, confianza_pct, bcs_conf = estimacion_service.estimar(
        morfometria=morfo_stub,
        imagen_lateral=img_lateral_bgr,
        imagen_trasera=ruta_trasera
    )

    # ── Paso 6: Recuperación de la Morfometría Real calculada por el Space ──
    morfometria_real = getattr(estimacion_service, "_ultima_morfometria", None) or morfo_stub

    # ── Paso 7: Consolidación de índices de confianza ──
    confianza_vision = getattr(estimacion_service, "_ultima_confianza_vision", 1.0)
    confianza_final = round((confianza_vision * 0.6) + (bcs_conf * 0.4), 3)

    # ── Paso 8: Persistencia transaccional en PostgreSQL (Neon) ──
    medicion = Medicion(
        id=medicion_id,
        animal_id=animal_id,
        peso_estimado_kg=peso_kg,
        bcs=bcs_final,
        confianza=confianza_pct,
        img_lateral_url=url_lateral,
        img_trasera_url=url_trasera,
        morfometria=morfometria_real.model_dump() if hasattr(morfometria_real, "model_dump") else dict(morfometria_real),
        modelo_version=estimacion_service.version,
        procesado_por="hf-spaces:mobilesam+cnn+yolo+xgboost",
        notas=notas,
    )
    db.add(medicion)
    db.commit()
    db.refresh(medicion)

    interpretacion, recomendacion = estimacion_service.interpretar_bcs(bcs_final)

    # 9. Retorno estructurado hacia el cliente web
    return AnalisisResultado(
        peso_estimado_kg=peso_kg,
        bcs=bcs_final,
        confianza=round(confianza_final * 100, 1),
        interpretacion_bcs=interpretacion,
        recomendacion=recomendacion,
        morfometria=morfometria_real,
        medicion_id=medicion_id,
        procesado_en_segundos=round(time.time() - inicio, 2),
        confianza_peso=float(confianza_pct),
        confianza_bcs=float(bcs_conf),
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