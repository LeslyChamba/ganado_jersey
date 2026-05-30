"""
JER-WEIGHT — Estimacion Service  v5.0.0
  Modelo principal : EfficientNet-B0 híbrido ensemble (5 folds GroupKFold)
                     MAE validado: 7.48 ± 1.28 kg  (68 vacas Jersey)
  Modelo respaldo  : XGBoost v3 (si CNN falla o imagen inválida)
                     MAE validado: ~9.7 kg
  BCS              : YOLOv8 — ÚNICA instancia en toda la app (eliminado de VisionService)
  Ensemble         : promedio de 5 modelos (uno por fold GroupKFold)

CAMBIO CRÍTICO v5.0 vs v4.0 (RAM Render Free 512 MB):
  - YOLO BCS ya NO vive en VisionService → solo aquí (una instancia, no dos)
  - CNN ensemble: 5 × 18.7 MB = 93.7 MB RAM  (caben perfectamente)
  - SAM vit_b eliminado de vision_service.py → MobileSAM (~35 MB)
  - Presupuesto total estimado: ~274 MB de 512 MB disponibles

Firmas que cambian respecto a v4:
  - estimar() recibe imagen_lateral: Optional[np.ndarray]  (sin cambio)
  - estimar() recibe imagen_trasera: Optional[str]         (sin cambio)
  - estimar() retorna (peso_kg, bcs, confianza_pct, bcs_conf)  (sin cambio)
  ✓ analisis_controller.py NO necesita cambios de firma
"""
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path
from typing import Optional, Tuple, List
from torchvision import transforms
from PIL import Image

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

# ── Rutas ──────────────────────────────────────────────────
PROYECTO_DIR   = Path(__file__).resolve().parent.parent.parent
MODELS_DIR     = PROYECTO_DIR / "models_pt"
CNN_MODELS_DIR = MODELS_DIR / "models_ptA"   # subcarpeta con los 5 .pth

CNN_MODELS = [
    CNN_MODELS_DIR / f"hibrido_fold_{i}.pth"
    for i in range(1, 6)
]

MASS_MODEL_XGB = MODELS_DIR / "mass_model_v3.json"
FEAT_FILE_XGB  = MODELS_DIR / "feature_names_v3.txt"
BCS_MODEL      = MODELS_DIR / "best.pt"   # ← única instancia YOLO en la app

# ── Parámetros de normalización (dataset 68 vacas Jersey) ──
PESO_MEAN = 481.0
PESO_STD  = 74.7
BCS_MEAN  = 3.26;  BCS_STD  = 0.44
PT_MEAN   = 180.52; PT_STD  = 9.33
LC_MEAN   = 160.68; LC_STD  = 10.16

# ── IC basado en MAE validado ──────────────────────────────
MAE_CNN    = 7.48
MAE_XGB    = 9.70
MAE_FORMULA = 23.9
IC_FACTOR  = 1.96

PESO_MIN = 280.0
PESO_MAX = 750.0

# ── Transformación de inferencia ───────────────────────────
transform_inferencia = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    ),
])


# ── Arquitectura (debe coincidir exactamente con entrenamiento) ─
def _construir_modelo_hibrido(n_bio: int = 3) -> nn.Module:
    try:
        import timm
        backbone = timm.create_model(
            "efficientnet_b0", pretrained=False,
            num_classes=0, global_pool="avg"
        )
    except Exception:
        raise ImportError("timm no instalado: pip install timm")

    class ModeloHibrido(nn.Module):
        def __init__(self, backbone, n_vis, n_bio):
            super().__init__()
            self.backbone    = backbone
            self.visual_head = nn.Sequential(
                nn.Linear(n_vis, 512),
                nn.BatchNorm1d(512),
                nn.ReLU(),
                nn.Dropout(0.3),
            )
            self.bio_head = nn.Sequential(
                nn.Linear(n_bio, 32), nn.ReLU(),
                nn.Linear(32, 64),   nn.ReLU(),
            )
            self.fusion = nn.Sequential(
                nn.Linear(576, 256),
                nn.BatchNorm1d(256),
                nn.ReLU(), nn.Dropout(0.3),
                nn.Linear(256, 64), nn.ReLU(),
                nn.Dropout(0.2),    nn.Linear(64, 1),
            )

        def forward(self, img, bio):
            v = self.visual_head(self.backbone(img))
            b = self.bio_head(bio)
            return self.fusion(torch.cat([v, b], dim=1)).squeeze(1)

    n_vis = backbone.num_features
    return ModeloHibrido(backbone, n_vis, n_bio)


# ── Calibración SAM → cinta real (v4, sin cambios) ────────
def estimar_cinta_desde_sam(pt_sam: float, lc_sam: float) -> Tuple[float, float]:
    pt_real = pt_sam * 0.91 + 16.2
    lc_real = lc_sam * 0.88 + 18.5
    return round(pt_real, 1), round(lc_real, 1)


def calcular_peso_formula(pt: float, lc: float, bcs: float) -> float:
    """Fórmula Crevat-Quittet calibrada Jersey. Último recurso."""
    peso_base  = (pt ** 2 * lc) / 10800
    ajuste_bcs = 1.0 + (bcs - 3.0) * 0.04
    return round(max(PESO_MIN, min(PESO_MAX, peso_base * ajuste_bcs)), 1)


class EstimacionService:
    version = "5.0.0-hibrido-cnn-jersey"

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
        self._device      = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._modelos_cnn : List[nn.Module] = []
        self._yolo_bcs    = None   # ← ÚNICA instancia YOLO en toda la app
        self._xgb_mass    = None
        logger.info(f"EstimacionService v5.0 | device={self._device} | CNN 5 folds ~93.7 MB")

    # ── CNN ensemble — carga lazy ──────────────────────────
    def _get_modelos_cnn(self) -> List[nn.Module]:
        if self._modelos_cnn:
            return self._modelos_cnn
        cargados = []
        for ruta in CNN_MODELS:
            if not ruta.exists():
                logger.warning(f"CNN no encontrado: {ruta}")
                continue
            try:
                m     = _construir_modelo_hibrido(n_bio=3)
                state = torch.load(str(ruta), map_location=self._device)
                m.load_state_dict(state)
                m.to(self._device)
                m.eval()
                cargados.append(m)
                logger.info(f"CNN cargado: {ruta.name}")
            except Exception as e:
                logger.warning(f"Error cargando {ruta.name}: {e}")
        if not cargados:
            logger.error("No se cargó ningún modelo CNN — se usará XGBoost")
        else:
            logger.info(f"{len(cargados)}/5 CNN cargados (~{len(cargados)*18.7:.0f} MB RAM)")
        self._modelos_cnn = cargados
        return self._modelos_cnn

    # ── YOLO BCS — ÚNICA instancia en toda la aplicación ──
    def _get_yolo(self):
        """
        Esta es la ÚNICA instancia de YOLO BCS en todo el proceso.
        VisionService v5 ya NO carga YOLO — solo vive aquí.
        """
        if self._yolo_bcs is None:
            if not BCS_MODEL.exists():
                logger.warning(f"BCS_MODEL no encontrado: {BCS_MODEL}")
                return None
            try:
                from ultralytics import YOLO
                self._yolo_bcs = YOLO(str(BCS_MODEL))
                logger.info("YOLO BCS cargado (instancia única en la app)")
            except Exception as e:
                logger.warning(f"No se pudo cargar YOLO BCS: {e}")
        return self._yolo_bcs

    # ── XGBoost — respaldo ─────────────────────────────────
    def _get_xgb(self):
        if self._xgb_mass is None:
            if not MASS_MODEL_XGB.exists():
                return None
            try:
                import xgboost as xgb
                b = xgb.XGBRegressor()
                b.load_model(str(MASS_MODEL_XGB))
                self._xgb_mass = b
                logger.info("XGBoost v3 cargado (respaldo)")
            except Exception as e:
                logger.warning(f"No se pudo cargar XGBoost: {e}")
        return self._xgb_mass

    # ── Predicción BCS ─────────────────────────────────────
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
                bcs = float(nombres[top_idx])
            except (KeyError, ValueError):
                bcs = {0: 3.0, 1: 3.25, 2: 3.5, 3: 4.0, 4: 4.5}.get(top_idx, 3.0)
            logger.info(f"BCS YOLO: {bcs} conf:{confianza:.2f}")
            return bcs, confianza
        except Exception as e:
            logger.warning(f"Error BCS YOLO: {e} → BCS=3.0")
            return 3.0, 0.0

    # ── Preprocesar imagen para CNN (TTA) ──────────────────
    def _preprocesar_imagen(self, imagen_bgr: np.ndarray) -> Optional[torch.Tensor]:
        """
        Convierte imagen BGR → tensor normalizado con TTA:
        original + flip horizontal + center crop.
        Retorna tensor (3, 3, 224, 224).
        """
        try:
            img_rgb  = Image.fromarray(imagen_bgr[:, :, ::-1])
            t_base   = transform_inferencia(img_rgb)
            img_flip = img_rgb.transpose(Image.FLIP_LEFT_RIGHT)
            t_flip   = transform_inferencia(img_flip)
            w, h     = img_rgb.size
            margin   = int(min(w, h) * 0.06)
            img_crop = img_rgb.crop((margin, margin, w-margin, h-margin))
            t_crop   = transform_inferencia(img_crop)
            return torch.stack([t_base, t_flip, t_crop])  # (3, 3, 224, 224)
        except Exception as e:
            logger.warning(f"Error preprocesando imagen: {e}")
            return None

    # ── Predicción CNN ensemble ────────────────────────────
    def _predecir_cnn(
        self,
        imgs_tta : torch.Tensor,
        bcs      : float,
        pt_real  : float,
        lc_real  : float,
    ) -> Optional[float]:
        modelos = self._get_modelos_cnn()
        if not modelos:
            return None
        try:
            bio_norm = torch.tensor([
                (bcs     - BCS_MEAN) / BCS_STD,
                (pt_real - PT_MEAN)  / PT_STD,
                (lc_real - LC_MEAN)  / LC_STD,
            ], dtype=torch.float32).to(self._device)
            bio_batch  = bio_norm.unsqueeze(0).repeat(3, 1)   # (3, 3)
            imgs_batch = imgs_tta.to(self._device)             # (3, 3, 224, 224)
            predicciones_fold = []
            with torch.no_grad():
                for modelo in modelos:
                    preds_tta = modelo(imgs_batch, bio_batch).cpu().numpy()
                    preds_kg  = preds_tta * PESO_STD + PESO_MEAN
                    predicciones_fold.append(float(np.mean(preds_kg)))
            pred_final = float(np.mean(predicciones_fold))
            logger.info(
                f"CNN ensemble: folds={[round(p,1) for p in predicciones_fold]} "
                f"→ {pred_final:.1f} kg"
            )
            return pred_final
        except Exception as e:
            logger.warning(f"Error CNN: {e}")
            return None

    # ── Predicción XGBoost (respaldo) ─────────────────────
    def _predecir_xgb(self, pt: float, lc: float, bcs: float) -> Optional[float]:
        xgb_model = self._get_xgb()
        if xgb_model is None:
            return None
        try:
            vol         = pt ** 2 * lc
            pt_lc_ratio = pt / max(lc, 1.0)
            feat = pd.DataFrame([[
                pt, lc, bcs, vol, pt_lc_ratio,
                bcs*pt, bcs*vol, pt**2, lc**2, pt*bcs*lc
            ]], columns=[
                "pt", "lc", "bcs", "vol", "pt_lc_ratio",
                "bcs_pt", "bcs_vol", "pt_sq", "lc_sq", "pt_bcs_lc"
            ]).astype(np.float32)
            pred = float(xgb_model.predict(feat)[0])
            logger.info(f"XGBoost respaldo: {pred:.1f} kg")
            return pred if PESO_MIN <= pred <= PESO_MAX else None
        except Exception as e:
            logger.warning(f"Error XGBoost: {e}")
            return None

    # ── Método principal ───────────────────────────────────
    def estimar(
        self,
        morfometria    : MorfometriaData,
        imagen_lateral : Optional[np.ndarray] = None,
        imagen_trasera : Optional[str]        = None,
    ) -> Tuple[float, float, float, float]:
        """
        Retorna (peso_kg, bcs_score, confianza_pct, bcs_conf).
        imagen_lateral : ndarray BGR para CNN.
        imagen_trasera : ruta string en disco para YOLO BCS.
        """
        # ── BCS ─────────────────────────────────────────────
        if imagen_trasera is not None:
            bcs_score, bcs_conf = self._predecir_bcs(imagen_trasera)
        else:
            bcs_score = getattr(morfometria, "_bcs",      3.0)
            bcs_conf  = getattr(morfometria, "_bcs_conf", 0.0)

        # ── Calibración SAM → cinta ────────────────────────
        pt_real, lc_real = estimar_cinta_desde_sam(
            float(morfometria.perimetro_toracico_cm or 179.0),
            float(morfometria.largo_corporal_cm     or 156.0),
        )
        logger.info(f"Medidas calibradas: PT={pt_real:.1f} LC={lc_real:.1f} BCS={bcs_score:.2f}")

        # ── CNN híbrido (principal) ────────────────────────
        peso_cnn   = None
        metodo     = "xgboost_respaldo"
        confianza  = 50.0
        mae_modelo = MAE_XGB

        if imagen_lateral is not None:
            imgs_tta = self._preprocesar_imagen(imagen_lateral)
            if imgs_tta is not None:
                peso_cnn = self._predecir_cnn(imgs_tta, bcs_score, pt_real, lc_real)

        if peso_cnn is not None and PESO_MIN <= peso_cnn <= PESO_MAX:
            peso_final = peso_cnn
            metodo     = "cnn_hibrido_ensemble"
            confianza  = 92.0
            mae_modelo = MAE_CNN
            logger.info(f"CNN híbrido: {peso_final:.1f} kg")
        else:
            if peso_cnn is not None:
                logger.warning(f"CNN fuera de rango ({peso_cnn:.1f} kg) → XGBoost")
            peso_xgb = self._predecir_xgb(pt_real, lc_real, bcs_score)
            if peso_xgb is not None:
                peso_final = peso_xgb
                metodo     = "xgboost_respaldo"
                confianza  = 70.0
                mae_modelo = MAE_XGB
            else:
                peso_final = calcular_peso_formula(pt_real, lc_real, bcs_score)
                metodo     = "formula_calibrada"
                confianza  = 45.0
                mae_modelo = MAE_FORMULA

        # ── Intervalo de confianza ─────────────────────────
        factor_bcs = 1.0 + max(0.0, (0.7 - bcs_conf)) * 0.3
        ic = round(mae_modelo * factor_bcs * IC_FACTOR, 1)
        logger.info(f"Peso final ({metodo}): {peso_final:.1f} ±{ic} kg | conf={confianza:.0f}%")

        return (
            round(peso_final, 1),
            round(bcs_score, 2),
            round(confianza, 1),
            round(bcs_conf, 3),
        )

    def interpretar_bcs(self, bcs: float) -> Tuple[str, str]:
        for lo, hi, interp, rec in self.BCS_INTERPRETACIONES:
            if lo <= bcs < hi:
                return interp, rec
        if bcs < 0:
            return "Valor inválido", "BCS no puede ser negativo."
        return "Obesa", "Reducción inmediata. Riesgo metabólico alto."


estimacion_service = EstimacionService()