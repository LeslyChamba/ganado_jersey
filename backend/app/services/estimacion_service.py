"""
JER-WEIGHT — Estimacion Service  v2.4.0
  XGBoost (mass_model.json) + Fórmula morfométrica calibrada
  BCS predicho con YOLOv8 (best copy.pt) desde imagen trasera

Cambios v2.4:
  - pt_real y lc_real se estiman AUTOMÁTICAMENTE desde pt_img/lc_img
  - No requiere input manual del usuario — solo fotos
  - Función de conversión calibrada con 67 vacas Jersey:
      pt_real = 0.0387 × pt_img + 172.71  (clamp 155–205 cm)
      lc_real = 160.0 cm  (mediana dataset — lc_img no aporta señal útil)
  - MAE esperado: ~25–35 kg (vs 55 kg sin conversión)
"""
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

PROYECTO_DIR = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
MASS_MODEL   = PROYECTO_DIR / "models_pt" / "mass_model.json"
FEAT_FILE    = PROYECTO_DIR / "models_pt" / "feature_names.txt"
BCS_MODEL    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion\models_pt\best copy.pt")

PESO_MIN_KG = 300.0
PESO_MAX_KG = 750.0

BCS_CLASS_MAP = {0: 3.0, 1: 3.25, 2: 3.5, 3: 4.0, 4: 4.5}

# Orden EXACTO — debe coincidir con entrenar_mass_model.py v4
FEATURE_NAMES = [
    "ratio_lh",
    "htor_norm",
    "cad_norm",
    "perim_norm",
    "area_norm",
    "bcs",
    "pt_img",
    "lc_img",
    "vol_img",
    "pt_real",   # estimado automáticamente desde pt_img
    "lc_real",   # estimado automáticamente (mediana dataset)
    "vol_real",  # pt_real² × lc_real
]

PT_IMG_MIN, PT_IMG_MAX = 50.0,  420.0
LC_IMG_MIN, LC_IMG_MAX = 20.0,  500.0


# ══════════════════════════════════════════════════════════
# CONVERSIÓN SAM → CINTA (automática, sin input del usuario)
# ══════════════════════════════════════════════════════════

def estimar_cinta_desde_sam(pt_img: float, lc_img: float) -> Tuple[float, float]:
    """
    Estima las medidas de cinta a partir de las medidas SAM.
    Calibrada con regresión lineal sobre 67 vacas Jersey.

    pt_real: pendiente débil (+0.04) pero intercepto alto (172.71)
             → pt_img varía entre vacas pero pt_real es más estable
    lc_real: lc_img tiene pendiente NEGATIVA con lc_real (SAM mide
             encuentro→isquion, que no escala igual que la cinta)
             → se usa la mediana del dataset como mejor estimación

    MAE estimación: ±7 cm en pt_real, lc_real fijo en 160 cm
    """
    # pt_real estimado desde regresión lineal
    pt_real = 0.0387 * pt_img + 172.71
    pt_real = float(np.clip(pt_real, 155.0, 205.0))

    # lc_real: mediana del dataset (lc_img no aporta señal útil)
    lc_real = 160.0

    return pt_real, lc_real


# ══════════════════════════════════════════════════════════
# PREDICCIÓN BCS
# ══════════════════════════════════════════════════════════

def predecir_bcs(imagen_path: str) -> Tuple[float, float]:
    """
    Predice BCS desde imagen trasera con YOLOv8.
    Retorna (bcs_valor, confianza). Si falla → (3.0, 0.0).
    """
    try:
        from ultralytics import YOLO
        if not BCS_MODEL.exists():
            logger.warning(f"BCS_MODEL no encontrado: {BCS_MODEL}")
            return 3.0, 0.0

        res       = YOLO(str(BCS_MODEL))(imagen_path, verbose=False)
        probs     = res[0].probs
        top_idx   = int(probs.top1)
        confianza = float(probs.top1conf.item())

        nombres = res[0].names
        try:
            bcs_valor = float(nombres[top_idx])
        except (KeyError, ValueError):
            bcs_valor = BCS_CLASS_MAP.get(top_idx, 3.0)

        logger.info(f"BCS predicho: {bcs_valor} (conf={confianza:.2f})")
        return bcs_valor, confianza

    except Exception as e:
        logger.warning(f"Error prediciendo BCS: {e} → usando BCS=3.0")
        return 3.0, 0.0


# ══════════════════════════════════════════════════════════
# FÓRMULA MORFOMÉTRICA — respaldo de emergencia
# ══════════════════════════════════════════════════════════

def calcular_peso_formula(pt_real: float, lc_real: float, bcs: float) -> float:
    """
    Schaeffer calibrado con 69 vacas Jersey. K=10999.
    Solo se usa cuando XGBoost no está disponible.
    """
    BASE_K = 10999.0

    if bcs >= 4.0:
        BASE_K -= 250
    elif bcs <= 2.5:
        BASE_K += 250

    pt = float(np.clip(pt_real, 148.0, 205.0))
    lc = float(np.clip(lc_real, 108.0, 185.0))

    return round((pt ** 2 * lc) / BASE_K, 1)


# ══════════════════════════════════════════════════════════
# VALIDACIÓN DE FEATURES
# ══════════════════════════════════════════════════════════

def _validar_features_modelo() -> bool:
    if not FEAT_FILE.exists():
        logger.warning("feature_names.txt no encontrado — saltando validación")
        return True
    expected = FEAT_FILE.read_text().strip().split("\n")
    if expected != FEATURE_NAMES:
        logger.error(
            f"FEATURES DESINCRONIZADOS\n"
            f"  Modelo guardado : {expected}\n"
            f"  Código actual   : {FEATURE_NAMES}\n"
            f"  → Reentrenar con entrenar_mass_model.py v4"
        )
        return False
    return True


# ══════════════════════════════════════════════════════════
# SERVICIO PRINCIPAL
# ══════════════════════════════════════════════════════════

class EstimacionService:
    version = "2.4.0-sam-xgb"

    BCS_INTERPRETACIONES = [
        (0.0,  2.0,  "Caquéctica / Muy delgada",
                     "Atención urgente: suplementación energética inmediata."),
        (2.0,  2.5,  "Delgada",
                     "Aumentar ración energética. Revisar salud y parasitosis."),
        (2.5,  3.75, "Condición ideal",
                     " Condición corporal óptima para Jersey. Mantener dieta actual."),
        (3.75, 4.5,  "Sobre-condicionada",
                     "Reducir concentrados energéticos. Riesgo de cetosis en posparto."),
        (4.5,  5.5,  "Obesa",
                     "Reducción inmediata de concentrados. Riesgo metabólico alto."),
    ]

    def __init__(self):
        _validar_features_modelo()

    def estimar(
        self,
        morfometria:    MorfometriaData,
        imagen_trasera: Optional[str] = None,
    ) -> Tuple[float, float, float]:
        """
        Retorna (peso_kg, bcs, confianza_ml).
        Solo requiere morfometría de SAM e imagen trasera.
        No necesita ningún input manual del usuario.
        """
        m = getattr(morfometria, "_medidas_raw", {})

        # ── BCS ───────────────────────────────────────────────────────────
        if imagen_trasera is not None:
            bcs_score, bcs_conf = predecir_bcs(imagen_trasera)
        else:
            bcs_score = getattr(morfometria, "_bcs",      3.0)
            bcs_conf  = getattr(morfometria, "_bcs_conf", 0.0)

        # ── Medidas SAM ───────────────────────────────────────────────────
        pt_img_raw = m.get("pt")
        lc_img_raw = m.get("lc")
        sam_fallo  = (pt_img_raw is None or lc_img_raw is None)

        if sam_fallo:
            pt_img = 195.0
            lc_img = 120.0
            logger.warning("SAM no entregó pt/lc → usando defaults.")
        else:
            pt_img = float(pt_img_raw)
            lc_img = float(lc_img_raw)

        sam_ok = (
            not sam_fallo
            and PT_IMG_MIN <= pt_img <= PT_IMG_MAX
            and LC_IMG_MIN <= lc_img <= LC_IMG_MAX
        )

        # ── Conversión automática SAM → cinta ─────────────────────────────
        pt_real, lc_real = estimar_cinta_desde_sam(pt_img, lc_img)

        vol_img  = (pt_img  ** 2) * lc_img
        vol_real = (pt_real ** 2) * lc_real

        logger.info(
            f"SAM: pt_img={pt_img:.1f} lc_img={lc_img:.1f} | "
            f"Estimado: pt_real={pt_real:.1f} lc_real={lc_real:.1f} | "
            f"BCS={bcs_score}"
        )

        # ── Fórmula morfométrica (respaldo) ───────────────────────────────
        peso_formula = calcular_peso_formula(pt_real, lc_real, bcs_score)
        logger.info(f"Fórmula respaldo: {peso_formula} kg")

        # ── XGBoost ───────────────────────────────────────────────────────
        peso_xgboost: Optional[float] = None
        confianza_ml = 0.35

        try:
            import xgboost as xgb
            if MASS_MODEL.exists():
                b = xgb.Booster()
                b.load_model(str(MASS_MODEL))

                if b.num_features() != len(FEATURE_NAMES):
                    logger.warning(
                        f"mass_model desactualizado "
                        f"({b.num_features()} features, esperados {len(FEATURE_NAMES)})"
                    )
                    raise ValueError("modelo desactualizado")

                feat_values = [
                    m.get("ratio_lh",   1.0),
                    m.get("htor_norm",  0.41),
                    m.get("cad_norm",   0.30),
                    m.get("perim_norm", 1.0),
                    m.get("area_norm",  0.1),
                    bcs_score,
                    pt_img,     # SAM directo
                    lc_img,     # SAM directo
                    vol_img,    # pt_img² × lc_img
                    pt_real,    # estimado desde conversión
                    lc_real,    # estimado desde conversión
                    vol_real,   # pt_real² × lc_real
                ]

                feat = np.array([feat_values], dtype=np.float32)
                pred = float(b.predict(xgb.DMatrix(feat))[0])

                if PESO_MIN_KG <= pred <= PESO_MAX_KG:
                    peso_xgboost = pred
                    confianza_ml = 0.70 if sam_ok else 0.50
                    logger.info(f"XGBoost: {pred:.1f} kg ✓")
                else:
                    logger.warning(f"XGBoost fuera de rango ({pred:.1f} kg) → descartado")

        except Exception as e:
            logger.warning(f"XGBoost no disponible: {e}")

        # ── Blend ─────────────────────────────────────────────────────────
        if peso_xgboost is not None:
            if sam_ok:
                peso_final = (peso_formula * 0.30) + (peso_xgboost * 0.70)
                metodo     = "formula(30%)+xgboost(70%)"
            else:
                peso_final   = (peso_formula * 0.50) + (peso_xgboost * 0.50)
                metodo       = "formula(50%)+xgboost(50%) [SAM dudoso]"
                confianza_ml = min(confianza_ml, 0.45)
        else:
            peso_final   = peso_formula
            metodo       = "formula_solo"
            confianza_ml = 0.35

        logger.info(
            f"Peso final ({metodo}): {peso_final:.1f} kg | conf={confianza_ml:.2f}"
        )
        return round(peso_final, 1), round(bcs_score, 2), round(confianza_ml, 3)

    def interpretar_bcs(self, bcs: float) -> Tuple[str, str]:
        for lo, hi, interp, rec in self.BCS_INTERPRETACIONES:
            if lo <= bcs < hi:
                return interp, rec
        if bcs < 0:
            return "Valor inválido", "⚠️ BCS no puede ser negativo."
        return "Obesa", "🚨 Reducción inmediata de concentrados. Riesgo metabólico alto."


estimacion_service = EstimacionService()
