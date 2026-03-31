# app/services/inference_service.py
"""
SERVICIO DE INFERENCIA — BovineAI
===================================
Pipeline real:
  imagen → OpenCV (morfometría) → XGBoost (peso) → resultado

El modelo de peso es XGBoost (no PyTorch).
El BCS lo ingresa el usuario en el formulario.
"""
import xgboost as xgb
import numpy as np
import logging
from pathlib import Path
from app.services.vision.morphometry import process_image, MorphometryResult
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ══════════════════════════════════════════════════════════
# SINGLETON DEL MODELO XGBOOST
# ══════════════════════════════════════════════════════════

class ModelRegistry:
    _mass_model: xgb.XGBRegressor | None = None

    @classmethod
    def load_mass_model(cls) -> xgb.XGBRegressor:
        if cls._mass_model is None:
            path = Path(settings.MASS_MODEL_PATH)
            if not path.exists():
                raise FileNotFoundError(
                    f"Modelo de masa no encontrado en: {path}\n"
                    f"Guárdalo con: model.save_model('{path}')"
                )
            logger.info(f"Cargando modelo XGBoost desde {path}")
            model = xgb.XGBRegressor()
            model.load_model(str(path))
            cls._mass_model = model
            logger.info("Modelo de masa cargado")
        return cls._mass_model


# ══════════════════════════════════════════════════════════
# RESULTADO DE INFERENCIA
# ══════════════════════════════════════════════════════════

class InferenceResult:
    def __init__(self, masa_kg, masa_confianza, bcs_score, morfometria):
        self.masa_kg = round(masa_kg, 1)
        self.masa_margen_error_kg = round(abs(masa_kg * 0.06), 1)
        self.masa_confianza = round(masa_confianza, 4)
        self.bcs_score = round(max(1.0, min(5.0, bcs_score)), 2)
        self.bcs_confianza = 1.0
        self.morfometria = {
            "largo_corporal_cm": morfometria.largo_corporal_cm,
            "altura_cruz_cm": morfometria.altura_cruz_cm,
            "perimetro_toracico_cm": morfometria.perimetro_toracico_cm,
            "ancho_cadera_cm": morfometria.ancho_cadera_cm,
        }
        self.vision_confidence = morfometria.confidence
        self.scale_found = morfometria.scale_found


# ══════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════

async def predict(image_bytes: bytes, bcs: float) -> InferenceResult:
    """
    Pipeline completo: imagen + BCS del usuario → peso estimado.

    Parámetros:
        image_bytes:  bytes de la imagen recibida por FastAPI
        bcs:          condición corporal ingresada por el usuario (1.0–5.0)
    """
    # 1. Visión computacional → morfometría
    logger.info("Iniciando extracción morfométrica...")
    morph = process_image(image_bytes)
    # Escala: altura promedio Jersey configurada en settings
    # Para ajustar: cambia JERSEY_ALTURA_PROMEDIO_CM en .env

    # 2. Construir vector de features para XGBoost
    # ORDEN EXACTO del entrenamiento:
    # ["area_norm", "ratio_lh", "perimeter_norm", "bcs", "pt", "lc", "volumen_aprox"]
    pt = morph.perimetro_toracico_cm
    lc = morph.largo_corporal_cm
    volumen_aprox = (pt ** 2) * lc

    feature_vector = np.array([[
        morph.area_norm,
        morph.ratio_lh,
        morph.perimeter_norm,
        bcs,
        pt,
        lc,
        volumen_aprox,
    ]], dtype=np.float32)

    # 3. Predicción XGBoost
    model = ModelRegistry.load_mass_model()
    masa_pred = float(model.predict(feature_vector)[0])

    # 4. Confianza compuesta
    confianza = _calcular_confianza(morph)

    logger.info(
        f"Predicción: {masa_pred:.1f} kg | BCS: {bcs} | "
        f"Confianza: {confianza:.2f} | Escala: {'OK' if morph.scale_found else 'FALLBACK'}"
    )

    return InferenceResult(
        masa_kg=masa_pred,
        masa_confianza=confianza,
        bcs_score=bcs,
        morfometria=morph,
    )


def _calcular_confianza(morph: MorphometryResult) -> float:
    """
    Confianza compuesta:
      - Segmentación limpia → hasta 0.6
      - Referencia de escala encontrada → +0.4
    """
    base = morph.confidence * 0.6
    scale_bonus = 0.4 if morph.scale_found else 0.0
    return round(min(base + scale_bonus, 1.0), 3)
