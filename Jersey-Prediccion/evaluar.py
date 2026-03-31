"""
JER-WEIGHT — Evaluación Batch  v1
===================================
Procesa múltiples vacas desde carpetas y genera reporte completo.

Estructura de carpetas:
  CARPETA_LATERAL/   → V2 (18).jpg, V37 (5).jpg, ...
  CARPETA_TRASERA/   → V2 (10).jpg, V37 (12).jpg, ...

Salida:
  debug_batch/
    V2/
      debug_lateral_V2.jpg
      debug_trasera_V2.jpg
    V37/
      ...
  resultados_batch.csv
  resultados_batch_resumen.txt

Uso:
  python evaluar_batch.py
  python evaluar_batch.py --sin-roboflow
  python evaluar_batch.py --vacas V2 V37 V53
"""

import sys, time, argparse, traceback
import numpy as np
import cv2
import pandas as pd
from pathlib import Path

# ══════════════════════════════════════════════════════════
# ① EDITA ESTAS RUTAS ANTES DE CORRER
# ══════════════════════════════════════════════════════════

PROYECTO_DIR    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
MASS_MODEL      = PROYECTO_DIR / "models_pt" / "mass_model.json"
FEAT_FILE       = PROYECTO_DIR / "models_pt" / "feature_names.txt"
SAM_MODEL       = PROYECTO_DIR / "models_pt" / "sam_vit_b.pth"
BCS_MODEL       = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion\models_pt\best copy.pt")

CARPETA_LATERAL = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\Dataset-Vacas\V1")
CARPETA_TRASERA = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\BCS\imagenes_recortadas")
CSV_PESOS       = PROYECTO_DIR / "pesos_vacas_PLANTILLA.csv"

CARPETA_DEBUG   = PROYECTO_DIR / "debug_batch"
REPORTE_CSV     = PROYECTO_DIR / "resultados_batch.csv"
REPORTE_TXT     = PROYECTO_DIR / "resultados_batch_resumen.txt"

ROBOFLOW_API_KEY = "UjQmJp4eMxIZASwVa7Kk"
ROBOFLOW_MODEL   = "cattle-body-pfmdu/1"

# Vacas a evaluar — 20 representativas para la tesis
VACAS_DEFAULT = [
    "V67","V53","V63","V30","V31","V35",        # <380 kg (todas)
    "V23","V28","V5","V24","V45",               # 380-500 kg
    "V27","V8","V7","V66","V64",               # 500-580 kg
    "V65","V60","V11","V34","V16","V51","V68",  # >580 kg (todas)
]

sys.path.insert(0, str(PROYECTO_DIR))

# ══════════════════════════════════════════════════════════
# ② CONSTANTES — IDÉNTICAS A probar_imagen.py
# ══════════════════════════════════════════════════════════

LC_FACTOR_POR_RANGO = [
    (0,    70,  2.539),
    (70,   100, 1.803),
    (100,  130, 1.400),
    (130,  999, 1.070),
]
BCS_PT_ANCHOR  = {3.00:179.0, 3.25:178.0, 3.50:181.0, 4.00:189.0, 4.50:197.0}
PT_IMG_MEDIAN  = 185.0
PT_IMG_ESCALA  = 0.338
AC_REF         = 123.0
PESO_RANGO_BCS = {3.00:(303,520),3.25:(340,530),3.50:(360,560),4.00:(390,640),4.50:(430,702)}
FEATURES       = [
    "ratio_lh","htor_norm","cad_norm","perim_norm","area_norm",
    "bcs","pt_img","lc_img","vol_img","pt_real","lc_real","vol_real",
]


def get_lc_factor(lc):
    for lo, hi, f in LC_FACTOR_POR_RANGO:
        if lo <= lc < hi: return f
    return 1.619

def get_pt_real_est(pt_img, bcs):
    anchor = BCS_PT_ANCHOR.get(round(bcs * 4) / 4, 180.0)
    return float(np.clip(anchor + (pt_img - PT_IMG_MEDIAN) * PT_IMG_ESCALA, 155.0, 205.0))

def clamp_bcs(peso, bcs):
    lo, hi = PESO_RANGO_BCS.get(round(bcs * 4) / 4, (280, 720))
    return float(np.clip(peso, lo, hi))

def formula(pt, lc, bcs):
    K = 10999.0
    if bcs >= 4.0: K -= 250
    if bcs <= 2.5: K += 250
    return round((np.clip(pt*0.838,148,198)**2 * np.clip(lc*0.766,108,148)) / K, 1)


# ══════════════════════════════════════════════════════════
# ③ BUSCAR IMAGEN DE UNA VACA EN UNA CARPETA
# ══════════════════════════════════════════════════════════

def buscar_imagen(carpeta: Path, vaca_id: str) -> Path:
    """Busca la imagen del medio del conjunto de fotos de la vaca."""
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        # Patrones: "V2 (18).jpg", "V2(18).jpg", "V2_18.jpg", "V2.jpg"
        candidatos = (
            sorted(carpeta.glob(f"{vaca_id} (*){ext}")) or
            sorted(carpeta.glob(f"{vaca_id}(*){ext}")) or
            sorted(carpeta.glob(f"{vaca_id}_*{ext}")) or
            sorted(carpeta.glob(f"{vaca_id}{ext}"))
        )
        if candidatos:
            return candidatos[len(candidatos) // 2]  # imagen del medio
    return None


# ══════════════════════════════════════════════════════════
# ④ SAM — segmentación y medidas
# ══════════════════════════════════════════════════════════

_SAM_PREDICTOR = None  # cache para no recargar en cada vaca

def get_sam_predictor():
    global _SAM_PREDICTOR
    if _SAM_PREDICTOR is None:
        import torch
        from segment_anything import sam_model_registry, SamPredictor
        sam    = sam_model_registry["vit_b"](checkpoint=str(SAM_MODEL))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        sam.to(device=device)
        _SAM_PREDICTOR = SamPredictor(sam)
        print(f"  SAM cargado [{device}]")
    return _SAM_PREDICTOR


def segmentar_y_medir(img_bgr):
    """Devuelve (mask, contour, medidas_dict) desde imagen BGR."""
    h, w = img_bgr.shape[:2]
    predictor = get_sam_predictor()

    # Resetear estado interno antes de cada imagen nueva
    # Evita el crash de SAM en la segunda y siguientes vacas
    predictor.reset_image()
    predictor.set_image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

    cx, cy = w // 2, h // 2
    fg = np.array([[cx,cy],[cx-w//8,cy],[cx+w//8,cy],[cx,cy-h//8],[cx,cy+h//10],
                   [int(w*0.25),int(h*0.38)],[int(w*0.75),int(h*0.38)]])
    bg = np.array([[10,10],[w-10,10],[10,h-10],[w-10,h-10],[cx,10],[10,cy],[w-10,cy]])
    all_pts = np.vstack([fg, bg])
    all_lbl = np.array([1]*len(fg) + [0]*len(bg))

    masks, scores, _ = predictor.predict(
        point_coords=all_pts, point_labels=all_lbl, multimask_output=True)

    mejor = None; best_score = -1
    for mask, score in zip(masks, scores):
        fill = mask.sum() / (h * w)
        if 0.08 <= fill <= 0.80 and score > best_score:
            best_score = score; mejor = mask
    if mejor is None:
        mejor = masks[np.argmax(scores)]

    mb = mejor.astype(np.uint8) * 255
    k  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mb = cv2.morphologyEx(mb, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mb, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise ValueError("SAM no generó contorno")
    cnt = max(cnts, key=cv2.contourArea)
    mc  = np.zeros_like(mb)
    cv2.drawContours(mc, [cnt], -1, 255, -1)

    # ── Escala ──────────────────────────────────────────────────
    xb, yb, bw, bh = cv2.boundingRect(cnt)
    max_h_px = 0.0; x_ac = xb + bw // 2
    for xi in range(xb + int(bw*0.25), min(xb + int(bw*0.60), w)):
        ys = np.where(mc[:, xi] > 0)[0]
        if len(ys) >= 2:
            hh = float(ys[-1] - ys[0])
            if hh > max_h_px: max_h_px = hh; x_ac = xi
    if max_h_px < bh * 0.35: max_h_px = float(bh)
    px = max_h_px / AC_REF

    # ── Lomo y orientación ──────────────────────────────────────
    xs_v = []; tops_v = []
    for xi in range(xb, min(xb + bw, w)):
        ys = np.where(mc[:, xi] > 0)[0]
        if len(ys) >= 2: xs_v.append(xi); tops_v.append(float(ys[0]))
    xs_arr  = np.array(xs_v)
    tops_arr = np.array(tops_v)
    win = max(len(xs_arr) // 10, 5)
    tops_s = np.array([np.median(tops_arr[max(0,i-win):i+win+1]) for i in range(len(tops_arr))])

    tercio = bw // 3
    yt = yb + int(bh*0.05); ym = yb + int(bh*0.45)
    def dens(x0, x1):
        return sum(int(np.sum(mc[yt:ym, xi] > 0)) for xi in range(x0, min(x1, w))) / max(x1-x0, 1)
    orient = "derecha" if dens(xb, xb+tercio) < dens(xb+2*tercio, xb+bw) else "izquierda"

    mg = int(len(xs_arr) * 0.10)
    zona  = tops_s[mg:len(xs_arr)-mg]
    umbral = np.percentile(zona, 30); tol = bh * 0.05
    en_lomo = tops_s <= (umbral + tol)
    en_lomo[:mg] = False; en_lomo[len(xs_arr)-mg:] = False
    idx_lomo = np.where(en_lomo)[0]

    yi_p = yb + int(bh*0.18); yf_p = yb + int(bh*0.60); min_p = int(bh*0.10)
    def col_pata(lado):
        if lado == "derecha":
            for xi in range(min(xb+bw-int(bw*0.25), w)-1, xb+int(bw*0.45), -1):
                if len(np.where(mc[yi_p:yf_p, xi]>0)[0]) >= min_p: return xi
            return xb + bw - int(bw*0.25)
        else:
            for xi in range(xb+int(bw*0.19), min(xb+int(bw*0.50), w)):
                if len(np.where(mc[yi_p:yf_p, xi]>0)[0]) >= min_p: return xi
            return xb + int(bw*0.19)

    if len(idx_lomo) >= 5:
        x_enc = col_pata("derecha"   if orient == "derecha" else "izquierda")
        x_isq = col_pata("izquierda" if orient == "derecha" else "derecha")
    else:
        x_enc = int(np.percentile(xs_arr, 22)) if orient == "derecha" else int(np.percentile(xs_arr, 78))
        x_isq = int(np.percentile(xs_arr, 78)) if orient == "derecha" else int(np.percentile(xs_arr, 22))

    if abs(x_isq - x_enc) < bw * 0.20:
        x_enc = int(np.percentile(xs_arr, 22)) if orient == "derecha" else int(np.percentile(xs_arr, 78))
        x_isq = int(np.percentile(xs_arr, 78)) if orient == "derecha" else int(np.percentile(xs_arr, 22))

    lc_px = max(abs(x_isq - x_enc), 1)
    x_izq = min(x_enc, x_isq); x_der = max(x_enc, x_isq)

    # LC corregida
    lc_raw    = (lc_px / px) + 20
    lc_factor = get_lc_factor(lc_raw)
    lc_cm     = lc_raw * lc_factor

    # PT — miembro anterior
    if orient == "derecha":
        x_pt_b = int(np.clip(x_der - lc_px*0.22, 0, w-1))
    else:
        x_pt_b = int(np.clip(x_izq + lc_px*0.22, 0, w-1))

    ytt = yb + int(bh*0.05); ytb = yb + int(bh*0.46)
    h_tor = 0.0; x_pt = x_pt_b
    for xi in range(max(0, x_pt_b - int(lc_px*0.05)), min(w, x_pt_b + int(lc_px*0.05))):
        ys_i = np.where(mc[:, xi] > 0)[0]
        ys_t = ys_i[(ys_i >= ytt) & (ys_i <= ytb)]
        if len(ys_t) >= 2:
            h_i = float(ys_t[-1] - ys_t[0])
            if h_i > h_tor: h_tor = h_i; x_pt = xi
    if h_tor == 0:
        ys_fb = np.where(mc[:, x_pt_b] > 0)[0]
        ys_tb = ys_fb[(ys_fb >= ytt) & (ys_fb <= ytb)]
        h_tor = float(ys_tb[-1]-ys_tb[0]) if len(ys_tb) >= 2 else bh*0.4
    pt_cm = (h_tor * np.pi) / px

    # Cadera
    x_cad = int(np.clip(x_izq + lc_px*0.80, 0, w-1))
    yfs   = yb + int(bh*0.05); yfi = yb + int(bh*0.58)
    ys_c  = np.where(mc[:, x_cad] > 0)[0]
    ys_ct = ys_c[(ys_c >= yfs) & (ys_c <= yfi)]
    cad_h = float(ys_ct[-1]-ys_ct[0]) if len(ys_ct) >= 2 else 0.0

    # minAreaRect
    rect_min = cv2.minAreaRect(cnt)
    box_min  = np.int32(cv2.boxPoints(rect_min))
    _, (wr, hr), angulo = rect_min
    largo = float(max(wr, hr)); alto = float(min(wr, hr))
    ratio_lh = round(largo / alto, 4) if alto > 0 else 1.0

    area  = float(cv2.contourArea(cnt))
    perim = float(cv2.arcLength(cnt, True))
    area_mr   = largo * alto
    area_norm = round(area / area_mr, 5) if area_mr > 0 else round(area / (w*h), 5)

    m = {
        "pt":       round(pt_cm, 1),
        "lc":       round(lc_cm, 1),
        "lc_raw":   round(lc_raw, 1),
        "lc_factor":round(lc_factor, 3),
        "ratio_lh": ratio_lh,
        "htor_norm":round(h_tor / max_h_px, 4) if max_h_px > 0 else 0.0,
        "cad_norm": round(cad_h / max_h_px, 4) if max_h_px > 0 else 0.0,
        "perim_norm":round(perim / max_h_px, 4) if max_h_px > 0 else 1.0,
        "area_norm":area_norm,
        "px_per_cm":round(px, 4),
        "conf":     round(min(area / float(bw*bh), 1.0) if bw*bh > 0 else 0, 3),
        "angulo":   round(angulo, 1),
        "orient":   orient,
        # Para debug
        "xb":xb,"yb":yb,"bw":bw,"bh":bh,
        "x_enc":x_enc,"x_isq":x_isq,"x_pt":x_pt,"x_cad":x_cad,
        "x_ac":x_ac,"max_h_px":max_h_px,
        "ytt":ytt,"ytb":ytb,"yfs":yfs,"yfi":yfi,
        "box_min":box_min,
        "_xs":xs_v,"_tops":tops_s.tolist(),
    }
    return mc, cnt, m


# ══════════════════════════════════════════════════════════
# ⑤ DEBUG VISUAL LATERAL
# ══════════════════════════════════════════════════════════

def guardar_debug_lateral(img, mc, cnt, m, peso_est, bcs, ruta):
    ov  = img.copy()
    col = np.zeros_like(img); col[mc > 0] = [30, 200, 80]
    cv2.addWeighted(col, 0.30, ov, 0.70, 0, ov)
    cv2.drawContours(ov, [cnt],      -1, (40, 255, 120), 2)
    cv2.drawContours(ov, [m["box_min"]], 0, (255,255,255), 1)

    h_img, w_img = ov.shape[:2]
    x_enc=m["x_enc"]; x_isq=m["x_isq"]; x_pt=m["x_pt"]
    yfs=m["yfs"]; yfi=m["yfi"]; ytt=m["ytt"]; ytb=m["ytb"]

    # Lomo
    tops=m["_tops"]; xs=m["_xs"]
    if len(tops)==len(xs) and len(tops)>1:
        pts=[(int(xs[i]),int(tops[i])) for i in range(len(tops))]
        for i in range(len(pts)-1):
            cv2.line(ov, pts[i], pts[i+1], (0,220,255), 1)

    # LC
    ay = min(yfi+28, h_img-40)
    cv2.arrowedLine(ov,(x_enc,ay),(x_isq,ay),(0,210,255),2,tipLength=0.02)
    cv2.arrowedLine(ov,(x_isq,ay),(x_enc,ay),(0,210,255),2,tipLength=0.02)
    cv2.putText(ov, f"LC:{m['lc']:.0f}cm (raw:{m['lc_raw']:.0f} x{m['lc_factor']:.2f})",
                (x_enc+(x_isq-x_enc)//2-90, ay+22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,210,255), 2)

    # PT
    cv2.line(ov, (x_pt,ytt), (x_pt,ytb), (255,60,200), 2)
    cv2.putText(ov, f"PT:{m['pt']:.0f}cm", (x_pt+5, ytt+30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,60,200), 2)

    # Encuentro / isquion
    for xp, lbl in [(x_enc,"ENC"),(x_isq,"ISQ")]:
        xp_c = int(np.clip(xp, 0, w_img-1))
        ys_p  = np.where(mc[:, xp_c] > 0)[0]
        yp    = int(ys_p[0]) if len(ys_p) > 0 else m["yb"]
        cv2.circle(ov, (xp_c, yp), 9, (0,255,255), -1)
        cv2.putText(ov, lbl, (xp_c-15, yp-12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,255), 2)

    # Header
    lc_ok = 120 <= m["lc"] <= 200; pt_ok = 140 <= m["pt"] <= 210
    color  = (60,220,60) if (lc_ok and pt_ok) else (0,100,255)
    cv2.putText(ov,
        f"LC:{m['lc']:.0f} {'OK' if lc_ok else 'REV'}  "
        f"PT:{m['pt']:.0f} {'OK' if pt_ok else 'REV'}  "
        f"BCS:{bcs}  ang:{m['angulo']:.0f}  [{m['orient']}]  "
        f"Peso:{peso_est:.0f}kg",
        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

    cv2.imwrite(str(ruta), ov)


# ══════════════════════════════════════════════════════════
# ⑥ ROBOFLOW — segmentación trasera
# ══════════════════════════════════════════════════════════

def roboflow_trasera(img_path: Path, debug_ruta: Path = None) -> dict:
    try:
        import base64
        from inference_sdk import InferenceHTTPClient

        img = cv2.imread(str(img_path))
        if img is None: return {}
        h_i, w_i = img.shape[:2]
        _, buf = cv2.imencode(".jpg", img)
        b64    = base64.b64encode(buf).decode()

        client = InferenceHTTPClient(
            api_url="https://detect.roboflow.com", api_key=ROBOFLOW_API_KEY)
        res = client.infer(b64, model_id=ROBOFLOW_MODEL)
        if not res.get("predictions"):
            res = client.infer(b64, model_id="live_cattle/1")
        if not res.get("predictions"):
            return {}

        pred  = max(res["predictions"], key=lambda x: x["confidence"])
        pts   = np.array([[p["x"],p["y"]] for p in pred["points"]], dtype=np.int32)
        mask  = np.zeros((h_i,w_i), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        xb,yb,bw,bh = cv2.boundingRect(pts)

        # Ancho torácico y de caderas
        y_tt = yb+int(bh*0.20); y_tb = yb+int(bh*0.45)
        y_ct = yb+int(bh*0.45); y_cb = yb+int(bh*0.70)

        def max_ancho(y0, y1):
            mx = 0
            for yi in range(y0, min(y1, h_i)):
                xs = np.where(mask[yi,:]>0)[0]
                if len(xs) >= 2: mx = max(mx, int(xs[-1]-xs[0]))
            return mx

        ancho_tor = max_ancho(y_tt, y_tb)
        ancho_cad = max_ancho(y_ct, y_cb)

        # Escala propia de la foto trasera
        ppc   = bh / AC_REF if bh > 0 else 1.0
        at_cm = ancho_tor / ppc
        pt_r  = at_cm * np.pi

        # Debug trasera
        if debug_ruta:
            ov = img.copy(); overlay = img.copy()
            cv2.fillPoly(overlay, [pts], (0,200,100))
            cv2.addWeighted(ov, 0.6, overlay, 0.4, 0, ov)
            cv2.polylines(ov, [pts], True, (0,255,100), 2)
            cv2.rectangle(ov, (xb,yb), (xb+bw,yb+bh), (255,255,0), 1)
            # Línea ancho torácico
            ym_t = (y_tt+y_tb)//2
            xs_t = np.where(mask[min(ym_t,h_i-1),:]>0)[0]
            if len(xs_t) >= 2:
                cv2.line(ov,(xs_t[0],ym_t),(xs_t[-1],ym_t),(255,100,0),3)
                cv2.putText(ov, f"Tor:{ancho_tor}px={at_cm:.0f}cm PT={pt_r:.0f}cm",
                            (xs_t[0], ym_t-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,100,0), 2)
            # Línea caderas
            ym_c = (y_ct+y_cb)//2
            xs_c = np.where(mask[min(ym_c,h_i-1),:]>0)[0]
            if len(xs_c) >= 2:
                cv2.line(ov,(xs_c[0],ym_c),(xs_c[-1],ym_c),(100,0,255),3)
                cv2.putText(ov, f"Cad:{ancho_cad}px",
                            (xs_c[0], ym_c-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,0,255), 2)
            # Alto y escala
            cv2.line(ov,(xb+bw+5,yb),(xb+bw+5,yb+bh),(0,255,255),2)
            color_e = (60,220,60) if bh >= 200 else (0,100,255)
            cv2.putText(ov, f"H:{bh}px  px/cm={ppc:.2f}  {'OK' if bh>=200 else 'recortada'}",
                        (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_e, 2)
            cv2.imwrite(str(debug_ruta), ov)

        return {
            "ancho_tor_px": ancho_tor,
            "ancho_cad_px": ancho_cad,
            "alto_px"     : bh,
            "pt_rob"      : round(pt_r, 1),
            "fill"        : round(mask.sum()/(bw*bh), 3) if bw*bh>0 else 0,
            "confianza"   : round(pred["confidence"], 3),
        }
    except ImportError:
        print("    ⚠ pip install inference-sdk")
        return {}
    except Exception as e:
        print(f"    ⚠ Roboflow: {e}")
        return {}


# ══════════════════════════════════════════════════════════
# ⑦ PIPELINE COMPLETO PARA UNA VACA
# ══════════════════════════════════════════════════════════

def procesar_vaca(vaca_id, lat_path, tra_path, usar_roboflow, debug_dir):
    res = {k: None for k in [
        "vaca_id","img_lateral","img_trasera","peso_estimado","peso_formula",
        "peso_xgboost","bcs","bcs_conf","pt_img","lc_img","lc_raw","lc_factor",
        "angulo_deg","orientacion","confianza_sam","rob_pt","rob_alto_px",
        "rob_conf","tiempo_seg","error_proceso",
    ]}
    res["vaca_id"]     = vaca_id
    res["img_lateral"] = lat_path.name
    res["img_trasera"] = tra_path.name
    t0 = time.time()

    try:
        # Cargar y redimensionar lateral
        img = cv2.imread(str(lat_path))
        if img is None: raise ValueError(f"No se pudo leer {lat_path}")
        h0, w0 = img.shape[:2]
        if max(h0, w0) > 1280:
            f   = 1280 / max(h0, w0)
            img = cv2.resize(img, (int(w0*f), int(h0*f)))

        # Roboflow trasera (no bloquea si falla)
        datos_rob = {}
        if usar_roboflow:
            datos_rob = roboflow_trasera(
                tra_path,
                debug_ruta=debug_dir / f"debug_trasera_{vaca_id}.jpg"
            )
            if datos_rob:
                res["rob_pt"]      = datos_rob.get("pt_rob")
                res["rob_alto_px"] = datos_rob.get("alto_px")
                res["rob_conf"]    = datos_rob.get("confianza")

        # BCS
        bcs_score = 3.0; bcs_conf = 0.0
        try:
            from ultralytics import YOLO
            r_bcs    = YOLO(str(BCS_MODEL))(str(tra_path), verbose=False)
            probs    = r_bcs[0].probs
            top_idx  = int(probs.top1)
            bcs_conf = float(probs.top1conf.item())
            nombres  = r_bcs[0].names
            try:    bcs_score = float(nombres[top_idx])
            except: bcs_score = {0:3.0,1:3.25,2:3.5,3:4.0,4:4.5}.get(top_idx, 3.0)
        except Exception as e:
            print(f"    ⚠ BCS fallback 3.0: {e}")
        res["bcs"] = bcs_score; res["bcs_conf"] = round(bcs_conf*100, 1)

        # SAM + medidas
        mc, cnt, m = segmentar_y_medir(img)

        # Debug lateral
        guardar_debug_lateral(
            img, mc, cnt, m,
            peso_est=0,      # se actualiza más abajo
            bcs=bcs_score,
            ruta=debug_dir / f"debug_lateral_{vaca_id}.jpg"
        )

        pt  = m["pt"]; lc = m["lc"]

        # ratio_lh normalizado — siempre >= 1, consistente con entrenamiento v6
        ratio_lh_norm = m["ratio_lh"]
        if ratio_lh_norm > 0:
            ratio_lh_norm = max(ratio_lh_norm, 1.0 / ratio_lh_norm)

        # Schaeffer con BCS anchor — respaldo si XGBoost falla
        BCS_ANCHOR_F = {3.00:179.0, 3.25:178.0, 3.50:181.0, 4.00:189.0, 4.50:197.0}
        anchor   = BCS_ANCHOR_F.get(round(bcs_score*4)/4, 180.0)
        peso_sch = round((anchor**2 * 160.0) / 10999.0, 1)

        # Fix 1+2: solo XGBoost sin blend ni clamp
        peso_xgb = None
        try:
            import xgboost as xgb
            if MASS_MODEL.exists():
                b = xgb.Booster(); b.load_model(str(MASS_MODEL))
                if b.num_features() == len(FEATURES):
                    pt_r = get_pt_real_est(pt, bcs_score)
                    lc_r = 160.0
                    feat = np.array([[
                        ratio_lh_norm, m["htor_norm"], m["cad_norm"],  # ← normalizado
                        m["perim_norm"], m["area_norm"],
                        bcs_score, pt, lc, pt**2*lc, pt_r, lc_r, pt_r**2*lc_r
                    ]], dtype=np.float32)
                    pred = float(b.predict(xgb.DMatrix(feat))[0])
                    if 200 <= pred <= 750:
                        peso_xgb = round(pred, 1)
        except Exception as e:
            print(f"    ⚠ XGBoost: {e}")

        # Solo XGBoost, sin blend ni clamp
        masa = peso_xgb if peso_xgb is not None else peso_sch

        # Redibujar debug lateral con el peso final
        guardar_debug_lateral(img, mc, cnt, m, masa, bcs_score,
                              ruta=debug_dir / f"debug_lateral_{vaca_id}.jpg")

        res.update({
            "peso_estimado" : round(masa, 1),
            "peso_schaeffer": peso_sch,   # antes peso_f — ahora Schaeffer BCS
            "peso_xgboost"  : peso_xgb,
            "pt_img"        : pt,
            "lc_img"        : lc,
            "lc_raw"        : m["lc_raw"],
            "lc_factor"     : m["lc_factor"],
            "ratio_lh_norm" : ratio_lh_norm,
            "angulo_deg"    : m["angulo"],
            "orientacion"   : m["orient"],
            "confianza_sam" : round(m["conf"]*100, 1),
            "tiempo_seg"    : round(time.time()-t0, 1),
        })

    except Exception as e:
        res["error_proceso"] = str(e)
        res["tiempo_seg"]    = round(time.time()-t0, 1)
        traceback.print_exc()

    return res


# ══════════════════════════════════════════════════════════
# ⑧ MAIN
# ══════════════════════════════════════════════════════════

parser = argparse.ArgumentParser()
parser.add_argument("--sin-roboflow", action="store_true")
parser.add_argument("--vacas", nargs="+", default=None)
args = parser.parse_args()

vacas = args.vacas if args.vacas else VACAS_DEFAULT

# Validar modelos
for path, nombre in [(MASS_MODEL,"mass_model"),(SAM_MODEL,"SAM"),(BCS_MODEL,"BCS")]:
    if not path.exists():
        print(f"❌ {nombre} no encontrado: {path}"); sys.exit(1)

# Validar carpetas
for path, nombre in [(CARPETA_LATERAL,"lateral"),(CARPETA_TRASERA,"trasera")]:
    if not path.exists():
        print(f"❌ Carpeta {nombre} no encontrada: {path}"); sys.exit(1)

# Cargar pesos reales
pesos_reales = {}
if CSV_PESOS.exists():
    df_p = pd.read_csv(str(CSV_PESOS), sep=";", decimal=",")
    df_p = df_p.dropna(subset=["vaca_id","peso_real"])
    pesos_reales = dict(zip(df_p["vaca_id"].astype(str), df_p["peso_real"]))

SEP = "═" * 62
print(f"\n{SEP}")
print(f"  JER-WEIGHT — Evaluación Batch  ({len(vacas)} vacas)")
print(f"  Roboflow : {'desactivado' if args.sin_roboflow else 'activo'}")
print(f"{SEP}\n")

CARPETA_DEBUG.mkdir(parents=True, exist_ok=True)
resultados = []

for i, vid in enumerate(vacas, 1):
    lat = buscar_imagen(CARPETA_LATERAL, vid)
    tra = buscar_imagen(CARPETA_TRASERA, vid)

    if lat is None or tra is None:
        falta = "lateral" if lat is None else "trasera"
        print(f"[{i:2d}/{len(vacas)}] {vid:4s}  ⚠ imagen {falta} no encontrada — omitida")
        resultados.append({"vaca_id":vid,"error_proceso":f"imagen {falta} no encontrada"})
        continue

    print(f"[{i:2d}/{len(vacas)}] {vid:4s}  {lat.name[:30]:30s}", end=" ", flush=True)

    # Carpeta debug por vaca
    ddir = CARPETA_DEBUG / vid
    ddir.mkdir(parents=True, exist_ok=True)

    res = procesar_vaca(vid, lat, tra, not args.sin_roboflow, ddir)

    # Calcular error
    peso_r = pesos_reales.get(vid)
    res["peso_real"] = peso_r
    if peso_r and res["peso_estimado"]:
        res["error_kg"]  = round(res["peso_estimado"] - peso_r, 1)
        res["error_pct"] = round(abs(res["peso_estimado"] - peso_r) / peso_r * 100, 1)
    else:
        res["error_kg"] = res["error_pct"] = None

    resultados.append(res)

    if res["error_proceso"] is None:
        ok = "✓" if (res["error_pct"] or 999) < 15 else "⚠"
        msg = f"{ok}  {res['peso_estimado']} kg"
        if peso_r:
            msg += f"  (real={peso_r:.0f}  err={res['error_kg']:+.0f} kg  {res['error_pct']:.1f}%)"
        msg += f"  [{res['tiempo_seg']}s]"
        print(msg)
    else:
        print(f"❌  {res['error_proceso']}")


# ── Guardar CSV ───────────────────────────────────────────
df_res = pd.DataFrame(resultados)
df_res.to_csv(str(REPORTE_CSV), index=False)

# ── Estadísticas ──────────────────────────────────────────
df_ok = df_res[df_res["error_kg"].notna()].copy()

print(f"\n{SEP}")
print(f"  RESUMEN FINAL")
print(f"{SEP}")
print(f"  Procesadas con éxito : {len(df_ok)}")
print(f"  Con errores          : {len(df_res) - len(df_ok)}")

if len(df_ok) > 0:
    mae  = df_ok["error_kg"].abs().mean()
    rmse = float(np.sqrt((df_ok["error_kg"]**2).mean()))
    n40  = int((df_ok["error_kg"].abs() < 40).sum())
    n60  = int((df_ok["error_kg"].abs() < 60).sum())
    n    = len(df_ok)

    print(f"\n  MAE promedio   : {mae:.1f} kg")
    print(f"  RMSE           : {rmse:.1f} kg")
    print(f"  Error < 40 kg  : {n40}/{n} ({100*n40/n:.0f}%)")
    print(f"  Error < 60 kg  : {n60}/{n} ({100*n60/n:.0f}%)")

    bins   = [200,380,500,580,750]
    labels = ["<380 kg","380-500 kg","500-580 kg",">580 kg"]
    df_ok["rango"] = pd.cut(df_ok["peso_real"], bins=bins, labels=labels)

    print(f"\n  MAE por rango:")
    maes_rango = {}
    for r, g in df_ok.groupby("rango", observed=True):
        mae_r = g["error_kg"].abs().mean()
        maes_rango[r] = mae_r
        estado = "✅" if mae_r < 60 else "⚠"
        print(f"    {estado} {r:12s}: {mae_r:.1f} kg  (n={len(g)})")

    # Criterio tesis
    c1 = mae < 50
    c2 = n60/n >= 0.70
    c3 = all(v < 100 for v in maes_rango.values())
    print(f"\n  CRITERIO CONSISTENCIA:")
    print(f"    {'✅' if c1 else '❌'} MAE < 50 kg        → {mae:.1f} kg")
    print(f"    {'✅' if c2 else '❌'} ≥70% con err<60 kg → {100*n60/n:.0f}%")
    print(f"    {'✅' if c3 else '❌'} Ningún rango >100 kg")
    veredicto = "✅ CONSISTENTE — apto para tesis" if (c1 and c2 and c3) else "⚠  Necesita mejoras"
    print(f"\n  {veredicto}")

    # Tabla detallada
    print(f"\n  {'Vaca':5} {'Real':6} {'Est.':7} {'Error':8} {'%':6} {'BCS':5} {'PT':7} {'LC':7} {'Ang':5}")
    print(f"  {'-'*60}")
    for _, row in df_ok.sort_values("peso_real").iterrows():
        ok = "✓" if abs(row["error_kg"]) < 60 else "⚠"
        print(f"  {ok} {str(row['vaca_id']):4s} "
              f"{row['peso_real']:6.0f} "
              f"{row['peso_estimado']:7.1f} "
              f"{row['error_kg']:+8.1f} "
              f"{row['error_pct']:6.1f}% "
              f"{row['bcs']:5.2f} "
              f"{row['pt_img']:7.1f} "
              f"{row['lc_img']:7.1f} "
              f"{row['angulo_deg']:5.0f}°")

    # Guardar resumen TXT
    lineas = [
        "JER-WEIGHT — Reporte Evaluación Batch\n" + "="*50 + "\n",
        f"Vacas evaluadas  : {n}\n",
        f"MAE promedio     : {mae:.1f} kg\n",
        f"RMSE             : {rmse:.1f} kg\n",
        f"Error < 40 kg    : {n40}/{n} ({100*n40/n:.0f}%)\n",
        f"Error < 60 kg    : {n60}/{n} ({100*n60/n:.0f}%)\n",
        f"Veredicto        : {veredicto}\n\n",
        "MAE por rango:\n",
    ] + [f"  {r}: {v:.1f} kg\n" for r, v in maes_rango.items()] + [
        "\nDetalle por vaca:\n",
        df_ok[["vaca_id","peso_real","peso_estimado","error_kg","error_pct",
               "bcs","pt_img","lc_img"]].sort_values("peso_real").to_string(index=False),
    ]
    REPORTE_TXT.write_text("".join(lineas), encoding="utf-8")

print(f"\n  Resultados CSV : {REPORTE_CSV}")
print(f"  Resumen TXT    : {REPORTE_TXT}")
print(f"  Debug por vaca : {CARPETA_DEBUG}/")
print(f"{SEP}\n")
