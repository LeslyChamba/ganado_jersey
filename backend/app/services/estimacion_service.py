import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
from huggingface_hub import hf_hub_download
import os
from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

# ── Rutas relativas al archivo ─────────────────────────────────────────────
# --- Configuración de Hugging Face ---
REPO_ID = "lesly15/Peso"
HF_TOKEN = os.getenv("HF_TOKEN")

# Descarga de modelos desde Hugging Face
# Esto sobreescribe las rutas locales con las rutas temporales de descarga
MASS_MODEL = hf_hub_download(repo_id=REPO_ID, filename="mass_model_v3.json", token=HF_TOKEN)
FEAT_FILE  = hf_hub_download(repo_id=REPO_ID, filename="feature_names_v3.txt", token=HF_TOKEN)
BCS_MODEL  = hf_hub_download(repo_id=REPO_ID, filename="best.pt", token=HF_TOKEN)


PESO_MIN_KG = 280.0
PESO_MAX_KG = 750.0

# ── Features v3 (8 features, orden crítico para XGBoost) ──────────────────
FEATURE_NAMES = [
   "pt", "lc", "bcs", "vol", "pt_lc_ratio", 
    "bcs_pt", "bcs_vol", "pt_sq", "lc_sq", "pt_bcs_lc"
]

# ── Parámetros calibrados con 69 vacas Jersey reales ──────────────────────
# (Optimizados via L-BFGS-B minimizando MSE)
CAL = {
    "k_base":     10999.0,
    "k_bcs_alto":   250.0,   # bcs >= 4.0
    "k_bcs_bajo":   250.0,   # bcs <= 2.5
    "a_pt":       1.2129,    # antes era 0.0387 (medida SAM→real)
    "b_pt":      -27.56,     # antes era 172.71
    "a_lc":       0.8243,    # NUEVO: regresión continua (antes: 155/165 fijo)
    "b_lc":       10.01,
}

# ── Pesos de blend validados por RMSE (fórmula RMSE=23.9, XGB RMSE=9.7) ───
W_FORMULA  = 0.14   # antes: 0.30 (SAM ok) o 0.50
W_XGBOOST  = 0.86   # antes: 0.70 o 0.50

# ── RMSE de referencia para intervalo de confianza ────────────────────────
RMSE_BLEND   = 9.7    # RMSE CV del modelo (conservador)
RMSE_FORMULA = 23.9

PT_IMG_MIN, PT_IMG_MAX = 50.0, 420.0
LC_IMG_MIN, LC_IMG_MAX = 20.0, 500.0


# Factores calibrados: SAM sobreestima ~14% vs cinta real
# Regresión lineal calibrada con dataset real (recalcular con script)
# Forma: pt_real = PT_COEF * pt_sam + PT_INTERCEPT
# Ejecutar calibrar_factores_sam.py para obtener estos valores
SAM_PT_COEF      = 0.886    # ← reemplazar con output del script
SAM_PT_INTERCEPT = 0.0      # ← reemplazar con output del script
SAM_LC_COEF      = 0.826    # ← reemplazar con output del script
SAM_LC_INTERCEPT = 0.0      # ← reemplazar con output del script

def estimar_cinta_desde_sam(pt_img: float, lc_img: float) -> Tuple[float, float]:
    """
    Corrige sesgo SAM → cinta real usando regresión lineal calibrada
    con dataset real de vacas Jersey. Más preciso que factor fijo.
    """
    pt_real = float(np.clip(
        SAM_PT_COEF * pt_img + SAM_PT_INTERCEPT,
        148.0, 220.0
    ))
    lc_real = float(np.clip(
        SAM_LC_COEF * lc_img + SAM_LC_INTERCEPT,
        108.0, 200.0
    ))
    return pt_real, lc_real

def calcular_peso_formula(pt_real: float, lc_real: float, bcs: float) -> float:
    """Fórmula morfométrica calibrada (K ajustado con datos reales)."""
    K = CAL["k_base"]
    if bcs >= 4.0:
        K -= CAL["k_bcs_alto"]
    elif bcs <= 2.5:
        K += CAL["k_bcs_bajo"]
    pt = float(np.clip(pt_real, 148.0, 220.0))
    lc = float(np.clip(lc_real, 108.0, 200.0))
    return round((pt ** 2 * lc) / K, 1)


def _calcular_intervalo_confianza(sam_ok: bool, bcs_conf: float) -> float:
    """
    Intervalo de confianza dinámico basado en RMSE real del modelo.
    IC 95% = RMSE * 1.96
    """
    rmse_base = RMSE_BLEND if sam_ok else RMSE_FORMULA
    # Penalizar si BCS tiene baja confianza
    factor_bcs = 1.0 + max(0.0, (0.7 - bcs_conf)) * 0.5
    return round(rmse_base * factor_bcs * 1.96, 1)


def _validar_features_modelo() -> bool:
    if not FEAT_FILE.exists():
        logger.warning("feature_names_v3.txt no encontrado — saltando validacion")
        return True
    expected = FEAT_FILE.read_text().strip().split("\n")
    if expected != FEATURE_NAMES:
        logger.error(f"FEATURES DESINCRONIZADOS: {expected} vs {FEATURE_NAMES}")
        return False
    return True


class EstimacionService:
    version = "3.0.0-calibrado-jersey"

    BCS_INTERPRETACIONES = [
        (0.0,  2.0,  "Caquéctica / Muy delgada",
                     "Atención urgente: suplementación energética inmediata."),
        (2.0,  2.5,  "Delgada",
                     "Aumentar ración energética. Revisar salud y parasitosis."),
        (2.5,  3.75, "Condición ideal",
                     "Condición corporal óptima para Jersey. Mantener dieta actual."),
        (3.75, 4.5,  "Sobre-condicionada",
                     "Reducir concentrados energéticos. Riesgo de cetosis en posparto."),
        (4.5,  5.5,  "Obesa",
                     "Reducción inmediata de concentrados. Riesgo metabólico alto."),
    ]

    def __init__(self):
        self._yolo_bcs = None
        self._xgb_mass = None
        _validar_features_modelo()

    def _get_yolo(self):
        if self._yolo_bcs is None:
            if not BCS_MODEL.exists():
                logger.warning(f"BCS_MODEL no encontrado: {BCS_MODEL}")
                return None
            try:
                from ultralytics import YOLO
                logger.info(f"Cargando YOLO BCS desde {BCS_MODEL}")
                self._yolo_bcs = YOLO(str(BCS_MODEL))
            except Exception as e:
                logger.warning(f"No se pudo cargar YOLO: {e}")
        return self._yolo_bcs

    def _get_xgb(self):
        if self._xgb_mass is None:
            if not MASS_MODEL.exists():
                logger.warning(f"MASS_MODEL no encontrado: {MASS_MODEL}")
                return None
            try:
                import xgboost as xgb
                b = xgb.XGBRegressor()
                b.load_model(str(MASS_MODEL))
                b.get_booster().feature_names = FEATURE_NAMES
                logger.info("XGBoost mass_model_v3 cargado correctamente")
                self._xgb_mass = b
            except Exception as e:
                logger.warning(f"No se pudo cargar XGBoost: {e}")
        return self._xgb_mass

    def _predecir_bcs(self, imagen_path: str) -> Tuple[float, float]:
        yolo = self._get_yolo()
        if yolo is None:
            return 3.0, 0.0
        try:
            res       = yolo(imagen_path, verbose=False)
            probs     = res[0].probs
            top_idx   = int(probs.top1)
            confianza = float(probs.top1conf.item())
            nombres   = res[0].names
            try:
                bcs_valor = float(nombres[top_idx])
            except (KeyError, ValueError):
                bcs_valor = {0: 3.0, 1: 3.25, 2: 3.5, 3: 4.0, 4: 4.5}.get(top_idx, 3.0)
            logger.info(f"BCS predicho: {bcs_valor} (conf={confianza:.2f})")
            return bcs_valor, confianza
        except Exception as e:
            logger.warning(f"Error prediciendo BCS: {e}")
            return 3.0, 0.0

    def _build_features(
        self,
        pt: float, lc: float, bcs: float
    ) -> pd.DataFrame:
        """
        Construye el vector de 10 features para XGBoost.
        ORDEN CRÍTICO — debe coincidir con FEATURE_NAMES.
        """
        vol         = pt ** 2 * lc
        pt_lc_ratio = pt / max(lc, 1.0)
        bcs_pt      = bcs * pt
        bcs_vol     = bcs * vol
        pt_sq       = pt ** 2
        lc_sq       = lc ** 2
        pt_bcs_lc   = pt * bcs * lc
        
        # Creamos un diccionario con el mismo nombre exacto de la lista FEATURE_NAMES
        data = {
            "pt": [pt],
            "lc": [lc],
            "bcs": [bcs],
            "vol": [vol],
            "pt_lc_ratio": [pt_lc_ratio],
            "bcs_pt": [bcs_pt],
            "bcs_vol": [bcs_vol],
            "pt_sq": [pt_sq],
            "lc_sq": [lc_sq],
            "pt_bcs_lc": [pt_bcs_lc]
        }
        valores = [
            pt, lc, bcs, vol, pt_lc_ratio, 
            bcs_pt, bcs_vol, pt_sq, lc_sq, pt_bcs_lc
        ]
        df = pd.DataFrame([valores], columns=FEATURE_NAMES)
        
        # Convertimos a float32 por seguridad (a XGBoost le gustan los float32)
        return df.astype(np.float32)
    def estimar(
        self,
        morfometria:    MorfometriaData,
        imagen_trasera: Optional[str] = None,
    ) -> Tuple[float, float, float, float]:
        """
        Retorna (peso_kg, bcs_score, confianza).
        """
        # ── BCS ─────────────────────────────────────────────────────────────
        if imagen_trasera is not None:
            bcs_score, bcs_conf = self._predecir_bcs(imagen_trasera)
        else:
            bcs_score = getattr(morfometria, "_bcs",      3.0)
            bcs_conf  = getattr(morfometria, "_bcs_conf", 0.0)

        # ── Medidas SAM ──────────────────────────────────────────────────────
        pt_img_raw = morfometria.perimetro_toracico_cm
        lc_img_raw = morfometria.largo_corporal_cm

        sam_fallo = (pt_img_raw is None or lc_img_raw is None)
        if sam_fallo:
            _raw = getattr(morfometria, "_medidas_raw", {})
            pt_img_raw = _raw.get("pt")
            lc_img_raw = _raw.get("lc")
            sam_fallo  = (pt_img_raw is None or lc_img_raw is None)

        if sam_fallo:
            pt_img, lc_img = 195.0, 120.0
            logger.warning("SAM no entregó pt/lc → usando defaults.")
        else:
            pt_img = float(pt_img_raw)
            lc_img = float(lc_img_raw)

        sam_ok = (
            not sam_fallo
            and PT_IMG_MIN <= pt_img <= PT_IMG_MAX
            and LC_IMG_MIN <= lc_img <= LC_IMG_MAX
        )

        # ── Conversión SAM → medida real (CALIBRADA) ─────────────────────────
        pt_real, lc_real = estimar_cinta_desde_sam(pt_img, lc_img)

        logger.info(
            f"SAM: pt_img={pt_img:.1f} lc_img={lc_img:.1f} | "
            f"Real calibrado: pt={pt_real:.1f} lc={lc_real:.1f} | BCS={bcs_score}"
        )

        # ── Fórmula calibrada (respaldo) ─────────────────────────────────────
        peso_formula = calcular_peso_formula(pt_real, lc_real, bcs_score)
        logger.info(f"Fórmula calibrada: {peso_formula} kg")

        # ── XGBoost v3 ───────────────────────────────────────────────────────
        # ── XGBoost v3 ───────────────────────────────────────────────────────
        peso_xgboost: Optional[float] = None
        xgb_model = self._get_xgb()
        if xgb_model is not None:
            try:
                feat = self._build_features(pt_real, lc_real, bcs_score)
                # Al pasarle un DataFrame con las columnas, XGBoost no se confundirá
                pred = float(xgb_model.predict(feat)[0])
                if PESO_MIN_KG <= pred <= PESO_MAX_KG:
                    peso_xgboost = pred
                    logger.info(f"XGBoost v3: {pred:.1f} kg OK")
                else:
                    logger.warning(f"XGBoost fuera de rango ({pred:.1f} kg) → descartado")
            except Exception as e:
                logger.warning(f"Error en inferencia XGBoost: {e}")
                
        # ── Blend ponderado por RMSE validado ────────────────────────────────
        if peso_xgboost is not None and sam_ok:
            peso_final   = W_FORMULA * peso_formula + W_XGBOOST * peso_xgboost
            confianza_ml = 85.0
            metodo       = f"formula({W_FORMULA:.0%})+xgboost({W_XGBOOST:.0%})"
        elif peso_xgboost is not None:
            # SAM dudoso: blend más conservador
            peso_final   = 0.30 * peso_formula + 0.70 * peso_xgboost
            confianza_ml = 65.0
            metodo       = "formula(30%)+xgboost(70%) [SAM dudoso]"
        else:
            peso_final   = peso_formula
            confianza_ml = 45.0
            metodo       = "formula_calibrada_solo"

        # Intervalo de confianza dinámico (para mostrar en UI)
        intervalo = _calcular_intervalo_confianza(sam_ok, bcs_conf)
        logger.info(
            f"Peso final ({metodo}): {peso_final:.1f} ±{intervalo} kg "
            f"| conf={confianza_ml:.2f}"
        )

        return round(peso_final, 1), round(bcs_score, 2), round(confianza_ml, 3), round(bcs_conf, 3)

    def interpretar_bcs(self, bcs: float) -> Tuple[str, str]:
        for lo, hi, interp, rec in self.BCS_INTERPRETACIONES:
            if lo <= bcs < hi:
                return interp, rec
        if bcs < 0:
            return "Valor inválido", "BCS no puede ser negativo."
        return "Obesa", "Reducción inmediata de concentrados. Riesgo metabólico alto."


estimacion_service = EstimacionService()