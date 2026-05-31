"""
validacion_controller.py
Endpoint POST /api/v1/analisis/validar
Faltaba registrar este router en main.py
"""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from app.services.validacion_service import validacion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analisis", tags=["Validación de Imágenes"])

ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class FotoResultado(BaseModel):
    es_valida:           bool
    animal_detectado:    bool
    confianza_deteccion: float
    area_cobertura:      float
    posicion_correcta:   bool
    motivo:              str
    sugerencia:          str


class ValidacionResponse(BaseModel):
    lateral:    FotoResultado
    trasera:    FotoResultado
    par_valido: bool


@router.post("/validar", response_model=ValidacionResponse)
async def validar_fotos(
    imagen_lateral: UploadFile = File(...),
    imagen_trasera: UploadFile = File(...),
):
    for img, nombre in [(imagen_lateral, "lateral"), (imagen_trasera, "trasera")]:
        if img.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Imagen {nombre}: formato no soportado. Use JPG, PNG o WEBP.",
            )

    bytes_lateral = await imagen_lateral.read()
    bytes_trasera = await imagen_trasera.read()

    resultado = await validacion_service.validar_par(bytes_lateral, bytes_trasera)

    return ValidacionResponse(
        lateral=FotoResultado(**resultado.lateral.__dict__),
        trasera=FotoResultado(**resultado.trasera.__dict__),
        par_valido=resultado.par_valido,
    )