"""
validacion_service.py — v8.1 (Render — cliente del Neural Shield en HF)
────────────────────────────────────────────────────────────────────────
CAMBIO v8.1 vs v7.1:
  ─ v7.1: validaba localmente con OpenCV puro (contornos + umbral
    adaptativo). Detectaba "cualquier silueta grande bien encuadrada",
    SIN discriminar especie — un perro, una persona o cualquier objeto
    grande podía pasar como "apto".
  ─ v8.1: delega la validación biológica estricta al Neural Shield
    (YOLOv8, filtro Clase 19 = vaca) desplegado en el Space de
    Hugging Face, reusando el mismo patrón HTTP que ya usa
    VisionService para /predecir. Evita mantener dos lógicas de
    validación distintas y evita cargar un segundo modelo pesado
    en el free tier de Render.
"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ResultadoFoto:
    es_valida:           bool
    animal_detectado:    bool
    confianza_deteccion: float
    area_cobertura:      float
    posicion_correcta:   bool
    motivo:              str
    sugerencia:          str


@dataclass
class ResultadoPar:
    lateral:    ResultadoFoto
    trasera:    ResultadoFoto
    par_valido: bool


class ValidacionService:
    """Cliente HTTP del Neural Shield (YOLOv8, filtro Clase 19 = vaca) en Hugging Face."""

    async def validar_par(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> ResultadoPar:
        url = f"{settings.HF_SPACE_URL.rstrip('/')}/api/v1/analisis/validar"
        headers = {"x-inference-secret": settings.INFERENCE_API_SECRET}
        files = {
            "imagen_lateral": ("lateral.jpg", bytes_lateral, "image/jpeg"),
            "imagen_trasera": ("trasera.jpg", bytes_trasera, "image/jpeg"),
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, files=files)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error("Error llamando al Neural Shield (HF): %s", e)
            raise HTTPException(
                status_code=503,
                detail="No se pudo validar las imágenes (servicio de visión no disponible).",
            )

        lateral = ResultadoFoto(**data["lateral"])
        trasera = ResultadoFoto(**data["trasera"])

        return ResultadoPar(
            lateral=lateral,
            trasera=trasera,
            par_valido=data.get("par_valido", lateral.es_valida and trasera.es_valida),
        )


validacion_service = ValidacionService()