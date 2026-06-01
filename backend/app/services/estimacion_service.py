"""
JER-Weight — Estimacion Service  v6.0.0  (Render — cliente HTTP)
=================================================================
CAMBIO ARQUITECTURAL v6 vs v5:
  ─ v5: Render cargaba PyTorch + CNN + YOLO + SAM en su propia RAM (512 MB → OOM)
  ─ v6: Render actúa como cliente. Envía las imágenes al Motor de Inferencia
        alojado en Hugging Face Spaces (16 GB RAM) y recibe el resultado JSON.
        Render ya NO carga ningún modelo de IA.

RAM en Render después de v6: ~120 MB  (FastAPI + SQLAlchemy + httpx)
RAM en HF Spaces:            ~400 MB  (todos los modelos de IA)

Variable de entorno requerida en Render:
  INFERENCE_API_URL    : https://<tu-usuario>-jer-weight-inference.hf.space
  INFERENCE_API_SECRET : (mismo valor que en HF Space Secrets)

La firma pública de estimar() y interpretar_bcs() NO cambia
→ analisis_controller.py NO necesita ninguna modificación.
"""
import logging
import os
from typing import Optional, Tuple

import httpx

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

# ── Configuración ─────────────────────────────────────────
_HF_URL    = os.environ.get("INFERENCE_API_URL", "").rstrip("/")
_HF_SECRET = os.environ.get("INFERENCE_API_SECRET", "")

# Timeout generoso: MobileSAM puede tardar 8-15 s en CPU
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)


class EstimacionService:
    """
    Versión cliente HTTP de EstimacionService.
    La interfaz pública (estimar, interpretar_bcs, version) es idéntica a v5,
    por lo que analisis_controller.py no necesita cambios.
    """

    version = "6.0.0-http-client-hf"

    BCS_INTERPRETACIONES = [
        (0.0,  2.0,  "Caquéctica / Muy delgada",
                     "Atención urgente: suplementación energética inmediata."),
        (2.0,  2.5,  "Delgada",
                     "Aumentar ración energética. Revisar salud y parasitosis."),
        (2.5,  3.75, "Condición ideal",
                     "Condición corporal óptima para Jersey. Mantener dieta actual."),
        (3.75, 4.5,  "Sobre-condicionada",
                     "Reducir concentrados energéticos. Riesgo de cetosis posparto."),
        (4.5,  5.5,  "Obesa",
                     "Reducción inmediata de concentrados. Riesgo metabólico alto."),
    ]

    def __init__(self):
        # Almacenan el resultado del último llamado a estimar()
        # analisis_controller los lee para guardar morfometría real en DB
        self._ultima_morfometria:      Optional[MorfometriaData] = None
        self._ultima_confianza_vision: float                     = 1.0

        if not _HF_URL:
            logger.warning(
                "⚠️  INFERENCE_API_URL no configurada. "
                "Todas las estimaciones devolverán valores de fallback."
            )

    # ── Método principal ───────────────────────────────────
    def estimar(
        self,
        morfometria:     MorfometriaData,
        imagen_lateral:  Optional[object] = None,   # np.ndarray BGR
        imagen_trasera:  Optional[str]    = None,   # ruta en disco
    ) -> Tuple[float, float, float, float]:
        """
        Envía las imágenes al Motor de Inferencia en HF Spaces.

        Retorna (peso_kg, bcs_score, confianza_pct, bcs_conf).

        IMPORTANTE: imagen_lateral es un np.ndarray (viene de analisis_controller).
        Lo re-codificamos a JPEG en memoria para enviarlo como multipart/form-data.
        imagen_trasera es la ruta del archivo ya guardado en disco por el controller.
        """
        if not _HF_URL:
            logger.error("INFERENCE_API_URL no definida → fallback formula")
            return self._fallback_formula(morfometria)

        # ── Preparar bytes de imagen lateral ─────────────
        bytes_lateral = _ndarray_a_jpeg(imagen_lateral)
        if bytes_lateral is None:
            logger.error("No se pudo codificar imagen lateral → fallback")
            return self._fallback_formula(morfometria)

        # ── Preparar bytes de imagen trasera ──────────────
        bytes_trasera = _leer_archivo(imagen_trasera)
        if bytes_trasera is None:
            logger.error("No se pudo leer imagen trasera → fallback")
            return self._fallback_formula(morfometria)

        # ── Llamada HTTP al Motor de Inferencia ───────────
        try:
            respuesta = httpx.post(
                _HF_URL,  
                headers={"X-Inference-Secret": _HF_SECRET},
                headers={"X-Inference-Secret": _HF_SECRET},
                files={
                    "imagen_lateral": ("lateral.jpg", bytes_lateral, "image/jpeg"),
                    "imagen_trasera": ("trasera.jpg", bytes_trasera, "image/jpeg"),
                },
                timeout=_TIMEOUT,
            )
            respuesta.raise_for_status()
        except httpx.TimeoutException:
            logger.error("Motor de Inferencia: timeout → fallback formula")
            return self._fallback_formula(morfometria)
        except httpx.HTTPStatusError as e:
            logger.error(f"Motor de Inferencia HTTP {e.response.status_code}: {e.response.text}")
            return self._fallback_formula(morfometria)
        except Exception as e:
            logger.error(f"Error llamando al Motor de Inferencia: {e}")
            return self._fallback_formula(morfometria)

        # ── Parsear respuesta ──────────────────────────────
        try:
            data = respuesta.json()
            peso_kg      = float(data["peso_kg"])
            bcs          = float(data["bcs"])
            confianza    = float(data["confianza_pct"])
            bcs_conf     = float(data["bcs_conf"])

            # Guardar morfometría real y confianza_vision para analisis_controller
            self._ultima_confianza_vision = float(data.get("confianza_vision", 1.0))
            morfo_raw = data.get("morfometria", {})
            if morfo_raw:
                try:
                    self._ultima_morfometria = MorfometriaData(**morfo_raw)
                except Exception:
                    self._ultima_morfometria = None
            else:
                self._ultima_morfometria = None

            logger.info(
                f"Inferencia HF → peso={peso_kg:.1f} kg | BCS={bcs:.2f} | "
                f"conf={confianza:.0f}% | bcs_conf={bcs_conf:.2f}"
            )
            return round(peso_kg, 1), round(bcs, 2), round(confianza, 1), round(bcs_conf, 3)
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Respuesta inesperada del Motor de Inferencia: {e} | raw={respuesta.text[:300]}")
            return self._fallback_formula(morfometria)

    # ── Fallback cuando HF no responde ────────────────────
    def _fallback_formula(
        self, morfometria: MorfometriaData
    ) -> Tuple[float, float, float, float]:
        """
        Si el Motor de Inferencia no está disponible, usa la fórmula
        alométrica calibrada como último recurso.
        No requiere PyTorch ni ningún modelo.
        """
        pt  = float(morfometria.perimetro_toracico_cm or 179.0)
        lc  = float(morfometria.largo_corporal_cm     or 156.0)
        bcs = 3.0   # BCS promedio cuando no hay YOLO

        pt_real = pt * 0.91 + 16.2
        lc_real = lc * 0.88 + 18.5

        peso_base  = (pt_real ** 2 * lc_real) / 10800
        ajuste_bcs = 1.0 + (bcs - 3.0) * 0.04
        peso       = round(max(280.0, min(750.0, peso_base * ajuste_bcs)), 1)

        logger.warning(f"Fallback formula: {peso:.1f} kg (Motor HF no disponible)")
        return peso, bcs, 45.0, 0.0

    # ── Interpretación BCS (idéntica a v5 — sin dependencias) ─
    def interpretar_bcs(self, bcs: float) -> Tuple[str, str]:
        for lo, hi, interp, rec in self.BCS_INTERPRETACIONES:
            if lo <= bcs < hi:
                return interp, rec
        if bcs < 0:
            return "Valor inválido", "BCS no puede ser negativo."
        return "Obesa", "Reducción inmediata. Riesgo metabólico alto."


# ── Helpers ───────────────────────────────────────────────

def _ndarray_a_jpeg(imagen) -> Optional[bytes]:
    """Convierte np.ndarray BGR → bytes JPEG en memoria."""
    if imagen is None:
        return None
    try:
        import cv2
        import numpy as np
        ok, buf = cv2.imencode(".jpg", imagen, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes() if ok else None
    except Exception as e:
        logger.warning(f"Error codificando imagen lateral: {e}")
        return None


def _leer_archivo(ruta: Optional[str]) -> Optional[bytes]:
    """Lee un archivo de imagen desde disco."""
    if not ruta:
        return None
    try:
        with open(ruta, "rb") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Error leyendo imagen trasera ({ruta}): {e}")
        return None


# Instancia global — misma variable que usa analisis_controller.py
estimacion_service = EstimacionService()