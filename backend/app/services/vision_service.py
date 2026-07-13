"""
JER-Weight — Vision Service  v7.0.0  (Render — cliente del escudo de validación)
=================================================================================
CAMBIO v7 vs v6:
  ─ v6: stub puro, solo decodificaba la imagen, confianza fija 1.0.
  ─ v7: antes de decodificar/continuar, llama al endpoint
        POST /api/v1/analisis/validar del HF Space (validacion_service.py,
        OpenCV puro, <150ms, 0 MB extra). Si el par de fotos no pasa el
        escudo (no hay silueta de vaca, mal encuadre, foto borrosa, etc.),
        lanza HTTPException 422 con el motivo y la sugerencia concretos
        ANTES de tocar el pipeline pesado de /predecir.
"""
import logging
import numpy as np
import cv2
import httpx
from typing import Tuple

from fastapi import HTTPException
from app.schemas.schemas import MorfometriaData
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_DIM = 1280


class VisionService:
    """
    Cliente del escudo de validación (HF Space) + decodificador local.
    El análisis morfométrico y la inferencia real ocurren en HF Spaces.
    """

    async def analizar_imagenes(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> Tuple[MorfometriaData, np.ndarray, float]:

        # ── 1. Escudo de validación — ¿hay realmente una vaca? ──────────
        confianza_vision = await self._validar_par(bytes_lateral, bytes_trasera)

        # ── 2. Decodificar para uso posterior (thumbnail, etc.) ─────────
        nparr_lat = np.frombuffer(bytes_lateral, np.uint8)
        img_lat   = cv2.imdecode(nparr_lat, cv2.IMREAD_COLOR)

        if img_lat is None:
            raise ValueError("No se pudo decodificar la imagen lateral.")

        h, w = img_lat.shape[:2]
        if max(h, w) > MAX_DIM:
            f       = MAX_DIM / max(h, w)
            img_lat = cv2.resize(img_lat, (int(w * f), int(h * f)))

        # Stub morfometría — será reemplazada por los valores reales de HF
        morfo = MorfometriaData(
            alzada_cm               = 118.0,
            largo_corporal_cm       = 156.0,
            profundidad_toracica_cm = 65.4,
            ancho_caderas_cm        = 44.0,
            perimetro_toracico_cm   = 179.0,
            longitud_grupa_cm       = 44.0,
            ancho_grupa_cm          = 44.0,
        )

        logger.info(
            "VisionService v7: par validado (confianza=%.2f), imagen decodificada.",
            confianza_vision,
        )
        return morfo, img_lat, confianza_vision

    async def _validar_par(self, bytes_lateral: bytes, bytes_trasera: bytes) -> float:
        """
        Llama al escudo de validación OpenCV en el HF Space.
        Lanza 422 si el par de fotos no muestra un bovino en condiciones
        aceptables. Retorna la confianza promedio si es válido.
        """
        url = f"{settings.HF_SPACE_URL}/api/v1/analisis/validar"
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
            logger.error("Error llamando al escudo de validación: %s", e)
            raise HTTPException(
                status_code=503,
                detail="No se pudo validar las imágenes (servicio de visión no disponible).",
            )

        if not data.get("par_valido", False):
            lateral = data.get("lateral", {})
            trasera = data.get("trasera", {})
            fallos = [f for f in (lateral, trasera) if not f.get("es_valida", True)]
            motivo = " / ".join(f.get("motivo", "Imagen no válida.") for f in fallos)
            sugerencia = " ".join(f.get("sugerencia", "") for f in fallos)
            raise HTTPException(
                status_code=422,
                detail=f"{motivo} {sugerencia}".strip(),
            )

        conf_lat = data.get("lateral", {}).get("confianza_deteccion", 0.8)
        conf_tra = data.get("trasera", {}).get("confianza_deteccion", 0.8)
        return round((conf_lat + conf_tra) / 2, 3)


vision_service = VisionService()