"""
JER-WEIGHT — Vision Service  v5.0
  Foto lateral  → MobileSAM (vit_t) → silueta → OpenCV → medidas morfométricas
  Foto trasera  → guardada en disco para que EstimacionService corra YOLO BCS

CAMBIO CRÍTICO v5.0 (RAM Render Free 512 MB):
  - SAM vit_b  (~375 MB RAM)  →  MobileSAM vit_t (~35 MB RAM)   ahorro: 340 MB
  - YOLO BCS eliminado de aquí (vivía duplicado; solo vive en EstimacionService)
  - SAM se libera de RAM inmediatamente tras cada inferencia con gc.collect()
  - analizar_imagenes retorna (morfo, img_lat, confianza_vision) — 3 valores
    BCS y bcs_conf los obtiene EstimacionService directamente desde disco

Presupuesto RAM total con v5.0:
  MobileSAM ~35 MB + CNN 5×18.7 MB = 93.7 MB + YOLO ~25 MB + XGB ~30 MB
  + FastAPI/PyTorch runtime ~90 MB  ≈ 274 MB  ✓ (límite 512 MB)
"""
import gc
import logging
import numpy as np
import cv2
from pathlib import Path
from typing import Tuple, Optional

from app.schemas.schemas import MorfometriaData

logger = logging.getLogger(__name__)

PROYECTO_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR   = PROYECTO_DIR / "models_pt"
SAM_MODEL    = MODELS_DIR / "mobile_sam.pt"   # ← bajar de MobileSAM repo (~9 MB disco)

MAX_DIM = 1280


# ── MobileSAM ─────────────────────────────────────────────
def segmentar_con_sam(image_bgr: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Segmenta la vaca con MobileSAM vit_t.
    El modelo se carga, usa y libera dentro de esta función — nunca persiste en RAM.
    """
    import torch
    try:
        from mobile_sam import sam_model_registry, SamPredictor
        model_type = "vit_t"
    except ImportError:
        # Fallback a segment_anything si mobile_sam no está instalado
        logger.warning(
            "mobile_sam no encontrado. Instalar: "
            "pip install git+https://github.com/ChaoningZhang/MobileSAM.git  "
            "Usando segment_anything vit_b como fallback (más RAM)."
        )
        from segment_anything import sam_model_registry, SamPredictor
        model_type = "vit_b"

    if not SAM_MODEL.exists():
        raise FileNotFoundError(
            f"Modelo SAM no encontrado: {SAM_MODEL}\n"
            "Descarga mobile_sam.pt desde https://github.com/ChaoningZhang/MobileSAM "
            "y colócalo en models_pt/"
        )

    h, w   = image_bgr.shape[:2]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Cargar — se liberará al final
    sam = sam_model_registry[model_type](checkpoint=str(SAM_MODEL))
    sam.to(device=device)
    sam.eval()

    predictor = SamPredictor(sam)
    predictor.set_image(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))

    cx, cy  = w // 2, h // 2
    fg_pts  = np.array([[cx, cy], [cx-w//8, cy], [cx+w//8, cy],
                         [cx, cy-h//8], [cx, cy+h//10]])
    bg_pts  = np.array([[10, 10], [w-10, 10], [10, h-10], [w-10, h-10],
                         [cx, 10], [10, cy], [w-10, cy]])
    all_pts = np.vstack([fg_pts, bg_pts])
    all_lbl = np.array([1]*5 + [0]*7)

    masks, scores, _ = predictor.predict(
        point_coords=all_pts, point_labels=all_lbl, multimask_output=True
    )

    mejor_score, mejor_mask = -1, None
    for mask, score in zip(masks, scores):
        fill = mask.sum() / (h * w)
        if 0.08 <= fill <= 0.80 and score > mejor_score:
            mejor_score, mejor_mask = score, mask
    if mejor_mask is None:
        mejor_mask = masks[np.argmax(scores)]

    mask_bin = mejor_mask.astype(np.uint8) * 255
    k        = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k)

    cnts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # ── Liberar SAM de RAM antes de retornar ──────────────
    _liberar_sam(sam)

    if not cnts:
        return mask_bin, None

    main = max(cnts, key=cv2.contourArea)
    mc   = np.zeros_like(mask_bin)
    cv2.drawContours(mc, [main], -1, 255, -1)
    return mc, main


def _liberar_sam(sam_model) -> None:
    """Elimina el modelo SAM de RAM inmediatamente tras cada inferencia."""
    try:
        sam_model.cpu()
        del sam_model
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Aviso al liberar SAM: {e}")


# ── Orientación ───────────────────────────────────────────
def detectar_orientacion(mask, x_bb, y_bb, bw, bh):
    y_top, y_mid = y_bb + int(bh*0.05), y_bb + int(bh*0.45)
    tercio = bw // 3
    def densidad(x0, x1):
        t = 0
        for xi in range(x0, min(x1, mask.shape[1])):
            t += int(np.sum(mask[y_top:y_mid, xi] > 0))
        return t / max(x1 - x0, 1)
    return ("derecha"
            if densidad(x_bb, x_bb+tercio) < densidad(x_bb+2*tercio, x_bb+bw)
            else "izquierda")


def _col_pata(mask, x_bb, y_bb, bw, bh, lado):
    y_ini, y_fin = y_bb + int(bh*0.18), y_bb + int(bh*0.60)
    min_px = int(bh * 0.10)
    if lado == "derecha":
        x_ini = x_bb + int(bw*0.50)
        x_fin = x_bb + bw - int(bw*0.25)
        for xi in range(min(x_fin, mask.shape[1])-1, x_ini, -1):
            if len(np.where(mask[y_ini:y_fin, xi] > 0)[0]) >= min_px:
                return xi
        return x_fin
    else:
        x_ini = x_bb + int(bw*0.22)
        x_fin = x_bb + int(bw*0.50)
        for xi in range(x_ini, min(x_fin, mask.shape[1])):
            if len(np.where(mask[y_ini:y_fin, xi] > 0)[0]) >= min_px:
                return xi
        return x_ini


def detectar_lomo(mask, x_bb, y_bb, bw, bh, w_img):
    xs_v, tops_r = [], []
    for xi in range(x_bb, min(x_bb+bw, w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            xs_v.append(xi)
            tops_r.append(float(ys[0]))
    if len(xs_v) < 20:
        return x_bb, x_bb+bw, tops_r, xs_v, "derecha"
    xs_arr   = np.array(xs_v)
    tops_arr = np.array(tops_r)
    win      = max(len(xs_arr)//10, 5)
    tops_s   = np.array([
        np.median(tops_arr[max(0,i-win):i+win+1])
        for i in range(len(tops_arr))
    ])
    ori  = detectar_orientacion(mask, x_bb, y_bb, bw, bh)
    mg   = int(len(xs_arr) * 0.10)
    zona = tops_s[mg:len(xs_arr)-mg]
    umbral = np.percentile(zona, 30)
    tol    = bh * 0.05
    en_lomo = tops_s <= (umbral + tol)
    en_lomo[:mg] = False
    en_lomo[len(xs_arr)-mg:] = False
    idx = np.where(en_lomo)[0]
    if len(idx) >= 5:
        if ori == "derecha":
            x_enc = _col_pata(mask, x_bb, y_bb, bw, bh, "derecha")
            x_isq = _col_pata(mask, x_bb, y_bb, bw, bh, "izquierda")
        else:
            x_enc = _col_pata(mask, x_bb, y_bb, bw, bh, "izquierda")
            x_isq = _col_pata(mask, x_bb, y_bb, bw, bh, "derecha")
    else:
        if ori == "derecha":
            x_enc = int(np.percentile(xs_arr, 22))
            x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78))
            x_isq = int(np.percentile(xs_arr, 22))
    if abs(x_isq - x_enc) < bw * 0.20:
        if ori == "derecha":
            x_enc = int(np.percentile(xs_arr, 22))
            x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78))
            x_isq = int(np.percentile(xs_arr, 22))
    return x_enc, x_isq, tops_s.tolist(), xs_v, ori


def _seg(ys):
    if len(ys) < 2:
        return 0.0
    gaps = np.where(np.diff(ys) > 8)[0]
    if not len(gaps):
        return float(ys[-1] - ys[0])
    segs, p = [], 0
    for g in gaps:
        segs.append(ys[g] - ys[p])
        p = g + 1
    segs.append(ys[-1] - ys[p])
    return float(max(segs))


# ── Medidas morfométricas (idéntico a v4 — sin cambios) ──
def medir(image, mask, contour) -> dict:
    h_img, w_img = image.shape[:2]
    x_bb, y_bb, bw, bh = cv2.boundingRect(contour)
    max_h_px = 0.0
    x_ac     = 0
    for xi in range(x_bb+int(bw*0.25), min(x_bb+int(bw*0.60), w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            h = float(ys[-1] - ys[0])
            if h > max_h_px:
                max_h_px = h
                x_ac     = xi
    if max_h_px < bh * 0.35:
        max_h_px = float(bh)
        x_ac     = x_bb + bw // 2

    ALZADA_REF_CM = 118.0          # v4: alzada promedio Jersey
    px = max_h_px / ALZADA_REF_CM

    x_enc, x_isq, tops_s, xs_v, ori = detectar_lomo(mask, x_bb, y_bb, bw, bh, w_img)
    lc_px = max(abs(x_isq - x_enc), 1)
    x_izq = min(x_enc, x_isq)
    lc_cm = (lc_px / px) + 40.0   # v4: sesgo conservador

    x_pt  = np.clip(x_izq + int(lc_px*0.28), 0, w_img-1)
    y_fs  = y_bb + int(bh*0.05)
    y_fi  = y_bb + int(bh*0.58)
    ys_pt = np.where(mask[:, x_pt] > 0)[0]
    ys_tor = ys_pt[(ys_pt >= y_fs) & (ys_pt <= y_fi)]
    h_tor  = (float(ys_tor[-1]-ys_tor[0])
              if len(ys_tor) >= 2 else _seg(ys_pt))
    pt_cm  = (h_tor * 2.75) / px  # v4: factor elíptico bovino

    ys_ag  = np.where(mask[:, x_isq] > 0)[0]
    ag_cm  = (float(ys_ag[-1]-ys_ag[0])
              if len(ys_ag) >= 2 else max_h_px) / px
    x_cad  = np.clip(x_izq + int(lc_px*0.80), 0, w_img-1)
    ys_c   = np.where(mask[:, x_cad] > 0)[0]
    ys_ct  = ys_c[(ys_c >= y_fs) & (ys_c <= y_fi)]
    cad_cm = (float(ys_ct[-1]-ys_ct[0])
              if len(ys_ct) >= 2 else _seg(ys_c)) / px
    area   = float(cv2.contourArea(contour))
    perim  = float(cv2.arcLength(contour, True))
    htor_norm = h_tor / max_h_px if max_h_px > 0 else 0.0
    cad_h_px  = float(ys_ct[-1]-ys_ct[0]) if len(ys_ct) >= 2 else 0.0
    cad_norm  = cad_h_px / max_h_px if max_h_px > 0 else 0.0

    # Sanity checks (v4)
    if lc_cm > 165.0:
        logger.warning(f"LC anómalo ({lc_cm:.1f} cm) → recortado a 160.0")
        lc_cm = 160.0
    elif lc_cm < 110.0:
        lc_cm = 110.0
    if ag_cm > 50.0:
        ag_cm = 45.0
    if pt_cm > 185.0:
        logger.warning(f"PT anómalo ({pt_cm:.1f} cm) → recortado a 180.0")
        pt_cm = 180.0
    elif pt_cm < 130.0:
        pt_cm = 130.0

    return {
        "lc": round(lc_cm, 1), "ac": round(max_h_px/px, 1),
        "ag": round(ag_cm, 1), "pt": round(pt_cm, 1),
        "cadera": round(cad_cm, 1),
        "area_norm": round(area/(w_img*h_img), 5),
        "ratio_lh": round(lc_px/max_h_px if max_h_px > 0 else 1, 4),
        "perim_norm": round(perim/max_h_px if max_h_px > 0 else 1, 4),
        "htor_norm": round(htor_norm, 4), "cad_norm": round(cad_norm, 4),
        "px_per_cm": round(px, 4),
        "confidence": round(min(area/float(bw*bh), 1.0) if bw*bh > 0 else 0, 3),
        "orientacion": ori,
        "x_bb": x_bb, "y_bb": y_bb, "bw": bw, "bh": bh,
        "x_enc": x_enc, "x_isq": x_isq, "x_pt": x_pt,
        "x_cad": x_cad, "x_ac": x_ac,
        "max_h_px": max_h_px, "y_fs": y_fs, "y_fi": y_fi,
    }


# ── Servicio principal ────────────────────────────────────
class VisionService:
    """
    Solo segmentación MobileSAM + morfometría.
    BCS NO se calcula aquí — vive únicamente en EstimacionService._predecir_bcs().
    Esto evita tener dos instancias de YOLO en RAM simultáneamente.
    """

    async def analizar_imagenes(
        self,
        bytes_lateral: bytes,
        bytes_trasera: bytes,
    ) -> Tuple[MorfometriaData, np.ndarray, float]:
        """
        Retorna (morfo, img_lat, confianza_vision).
        img_lat se pasa a EstimacionService para la CNN híbrida.
        BCS/bcs_conf los calcula EstimacionService desde la ruta en disco.
        """
        nparr_lat = np.frombuffer(bytes_lateral, np.uint8)
        img_lat   = cv2.imdecode(nparr_lat, cv2.IMREAD_COLOR)
        nparr_tra = np.frombuffer(bytes_trasera, np.uint8)
        img_tra   = cv2.imdecode(nparr_tra, cv2.IMREAD_COLOR)

        if img_lat is None or img_tra is None:
            raise ValueError("No se pudieron decodificar las imágenes")

        # Redimensionar si son muy grandes
        for nombre, img in [("lateral", img_lat), ("trasera", img_tra)]:
            h0, w0 = img.shape[:2]
            if max(h0, w0) > MAX_DIM:
                f   = MAX_DIM / max(h0, w0)
                img = cv2.resize(img, (int(w0*f), int(h0*f)))
                if nombre == "lateral":
                    img_lat = img
                else:
                    img_tra = img

        # Segmentación MobileSAM — se carga y libera dentro de esta llamada
        mask, contour = segmentar_con_sam(img_lat)
        if contour is None:
            raise ValueError("MobileSAM no pudo segmentar la vaca en la foto lateral")

        m = medir(img_lat, mask, contour)
        logger.info(f"LC={m['lc']}cm PT={m['pt']}cm AC={m['ac']}cm")

        morfo = MorfometriaData(
            alzada_cm               = m["ac"],
            largo_corporal_cm       = m["lc"],
            profundidad_toracica_cm = round(m["pt"] / 2.75, 1),
            ancho_caderas_cm        = m["cadera"],
            perimetro_toracico_cm   = m["pt"],
            longitud_grupa_cm       = m.get("ag"),
            ancho_grupa_cm          = m["cadera"],
        )
        morfo._medidas_raw = m

        return morfo, img_lat, m["confidence"]


vision_service = VisionService()