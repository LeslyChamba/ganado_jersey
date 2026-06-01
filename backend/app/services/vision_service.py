"""
JER-Weight — Vision Service  v6.0.0  (Render — stub sin IA)
=============================================================
CAMBIO ARQUITECTURAL v6 vs v5:
  ─ v5: VisionService cargaba MobileSAM (~35 MB) en Render y extraía morfometría.
  ─ v6: VisionService en Render es un STUB.
        Solo decodifica las imágenes en memoria y retorna un MorfometriaData vacío.
        La morfometría REAL la calcula el Motor de Inferencia en HF Spaces
        (que ya devuelve también el peso y el BCS en el mismo JSON).

¿Por qué mantener VisionService en Render si ya no hace nada?
  → analisis_controller.py lo importa y llama a analizar_imagenes().
    Para no tocar el controller, mantenemos la firma idéntica.
    La morfometría que retorna este stub es ignorada por el nuevo
    EstimacionService (v6), que usa la del JSON de HF directamente.

Firma retornada (sin cambio):
  (MorfometriaData, np.ndarray, float)   → (morfo_stub, img_lat, confianza=1.0)
"""
import logging
import numpy as np
import cv2
from typing import Tuple

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

MAX_DIM = 1280


class VisionService:
    """
    Stub sin IA — solo decodifica imágenes.
    El análisis real ocurre en HF Spaces dentro del Motor de Inferencia.
    """

    async def analizar_imagenes(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> Tuple[MorfometriaData, np.ndarray, float]:
        """
        Decodifica las imágenes y retorna un MorfometriaData con valores
        por defecto (serán sobreescritos por los valores reales que
        devuelve el Motor de Inferencia en HF Spaces).

        La confianza retornada es 1.0 para que no penalice el cálculo
        de confianza_final en analisis_controller.py.
        """
        nparr_lat = np.frombuffer(bytes_lateral, np.uint8)
        img_lat   = cv2.imdecode(nparr_lat, cv2.IMREAD_COLOR)

        if img_lat is None:
            raise ValueError("No se pudo decodificar la imagen lateral.")

        # Redimensionar si es muy grande (para que httpx la envíe rápido)
        h, w = img_lat.shape[:2]
        if max(h, w) > MAX_DIM:
            f       = MAX_DIM / max(h, w)
            img_lat = cv2.resize(img_lat, (int(w * f), int(h * f)))

        # Stub morfometría — valores serán reemplazados por los de HF
        morfo = MorfometriaData(
            alzada_cm               = 118.0,
            largo_corporal_cm       = 156.0,
            profundidad_toracica_cm = 65.4,
            ancho_caderas_cm        = 44.0,
            perimetro_toracico_cm   = 179.0,
            longitud_grupa_cm       = 44.0,
            ancho_grupa_cm          = 44.0,
        )

        logger.info("VisionService v6 (stub): imagen decodificada, morfometría stub lista.")
        return morfo, img_lat, 1.0


vision_service = VisionService()