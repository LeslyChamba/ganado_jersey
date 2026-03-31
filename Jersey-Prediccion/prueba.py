"""
JER-WEIGHT — Pipeline completo  v4
  Foto trasera → Roboflow segmentación + YOLOv8 BCS
  Foto lateral → SAM → silueta exacta → medidas → XGBoost + Fórmula

Uso:
  python probar_imagen.py lateral.jpg trasera.jpg
  python probar_imagen.py lateral.jpg trasera.jpg --bcs 3.5
  python probar_imagen.py lateral.jpg trasera.jpg --sin-roboflow  # solo BCS, sin segmentación trasera

Mejoras v4:
  1. Roboflow segmenta la foto trasera → extrae ancho_tor y ancho_cad
  2. PT mejorado: combina h_tor lateral + ancho_tor trasera
  3. LC_CORR_FACTOR = 1.6189 — corrige subestimación sistemática de LC
  4. minAreaRect para ratio_lh preciso aunque la vaca esté inclinada
  5. Segunda pasada con ac_ref ajustado por rango de peso
  6. Puntos SAM adicionales en zona torácica para mejor segmentación

Requisitos extra:
  pip install inference-sdk
"""

import sys, time, argparse
import numpy as np
import cv2
from pathlib import Path

PROYECTO_DIR = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
MASS_MODEL   = PROYECTO_DIR / "models_pt" / "mass_model.json"
FEAT_FILE    = PROYECTO_DIR / "models_pt" / "feature_names.txt"
BCS_MODEL    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion\models_pt\best copy.pt")
SAM_MODEL    = PROYECTO_DIR / "models_pt" / "sam_vit_b.pth"
sys.path.insert(0, str(PROYECTO_DIR))

# ── Roboflow ───────────────────────────────────────────────────────
ROBOFLOW_API_KEY = "UjQmJp4eMxIZASwVa7Kk"
ROBOFLOW_MODEL   = "cattle-body-pfmdu/1"   # fallback: "live_cattle/1"

# ── Calibración LC dinámica (67 vacas Jersey) ─────────────────────
# El factor lc_real/lc_img varía según cuánto SAM midió la proyección:
#   lc_img bajo  (~70 cm)  → SAM captó solo parte → factor ~2.5
#   lc_img medio (~100 cm) → detección parcial     → factor ~1.8
#   lc_img alto  (~130 cm) → SAM midió bien        → factor ~1.1
# Factor fijo sobreestima cuando lc_img ya es alto (ej. 156→252 cm, error)
LC_FACTOR_POR_RANGO = [
    (0,    70,  2.539),
    (70,   100, 1.803),
    (100,  130, 1.400),
    (130,  999, 1.070),
]
LC_FACTOR_DEFAULT = 1.619   # fallback mediana global

def get_lc_factor(lc_img_cm: float) -> float:
    for lo, hi, factor in LC_FACTOR_POR_RANGO:
        if lo <= lc_img_cm < hi:
            return factor
    return LC_FACTOR_DEFAULT

ALZADA_POR_RANGO = {
    (0,   380): 120.0,
    (380, 500): 123.0,
    (500, 580): 126.0,
    (580, 999): 130.0,
}
AC_REF_DEFAULT = 123.0

# Orden EXACTO = feature_names.txt = entrenar_mass_model.py v4
FEATURE_NAMES = [
    "ratio_lh", "htor_norm", "cad_norm", "perim_norm", "area_norm",
    "bcs",
    "pt_img",  "lc_img",  "vol_img",
    "pt_real", "lc_real", "vol_real",
]

parser = argparse.ArgumentParser()
parser.add_argument("lateral")
parser.add_argument("trasera")
parser.add_argument("--bcs",          type=float, default=None)
parser.add_argument("--sin-roboflow", action="store_true",
                    help="Saltar segmentación Roboflow de la vista trasera")
args = parser.parse_args()

for p, n in [(args.lateral,"lateral"),(args.trasera,"trasera")]:
    if not Path(p).exists():
        print(f"\n❌ {n} no encontrada: {p}\n"); sys.exit(1)

SEP = "═" * 60
print(f"\n{SEP}")
print(f"  JER-WEIGHT — Pipeline SAM + Roboflow  v4")
print(f"{SEP}")
print(f"  Lateral    : {Path(args.lateral).name}")
print(f"  Trasera    : {Path(args.trasera).name}")
print(f"  BCS        : {'automático' if args.bcs is None else args.bcs}")
print(f"  Roboflow   : {'desactivado' if args.sin_roboflow else 'activo'}")
print(f"{SEP}\n")

for f, n in [(MASS_MODEL,"masa"),(BCS_MODEL,"BCS"),(SAM_MODEL,"SAM")]:
    if not f.exists():
        print(f"❌ Modelo {n}: {f}\n"); sys.exit(1)
print(f"  ✓ {MASS_MODEL.name}  ✓ {BCS_MODEL.name}  ✓ {SAM_MODEL.name}")

if FEAT_FILE.exists():
    expected = FEAT_FILE.read_text().strip().split("\n")
    if expected != FEATURE_NAMES:
        print(f"\n⚠  FEATURES DESINCRONIZADOS")
        print(f"   Modelo guardado : {expected}")
        print(f"   Código actual   : {FEATURE_NAMES}")
        print(f"   → Correr entrenar_mass_model.py antes de continuar\n")
        sys.exit(1)
    print(f"  ✓ feature_names.txt validado ({len(FEATURE_NAMES)} features)\n")


# ══════════════════════════════════════════════════════════
# ROBOFLOW — SEGMENTACIÓN TRASERA
# ══════════════════════════════════════════════════════════

def segmentar_trasera_roboflow(image_path: str) -> dict:
    """
    Segmenta la vista trasera con Roboflow y extrae medidas morfométricas:
      - ancho_tor_px : ancho del tórax en píxeles (zona superior del cuerpo)
      - ancho_cad_px : ancho de caderas en píxeles (zona media)
      - alto_px      : altura total de la silueta trasera
      - fill_ratio   : área silueta / área bounding box (proxy BCS)
      - ratio_tor_cad: ancho_tor / ancho_cad (forma corporal)
    """
    try:
        import base64
        from inference_sdk import InferenceHTTPClient

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo leer: {image_path}")

        img_h, img_w = img.shape[:2]
        _, buf = cv2.imencode(".jpg", img)
        img_b64 = base64.b64encode(buf).decode("utf-8")

        client = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=ROBOFLOW_API_KEY
        )

        result = client.infer(img_b64, model_id=ROBOFLOW_MODEL)

        if not result.get("predictions"):
            print("        ⚠ Roboflow: no detectó vaca → intentando modelo alternativo")
            result = client.infer(img_b64, model_id="live_cattle/1")

        if not result.get("predictions"):
            print("        ⚠ Roboflow: sin detección en ambos modelos")
            return {}

        pred       = max(result["predictions"], key=lambda x: x["confidence"])
        confianza  = pred["confidence"]
        points     = np.array([[p["x"], p["y"]] for p in pred["points"]], dtype=np.int32)

        # Máscara binaria desde polígono Roboflow
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)

        x_bb, y_bb, bw, bh = cv2.boundingRect(points)
        area_sil = int(np.sum(mask > 0))
        fill_ratio = area_sil / (bw * bh) if bw * bh > 0 else 0.0

        # Ancho torácico: zona superior 20-45% de la altura
        # (detrás de la cabeza, donde está el tórax)
        y_tor_top = y_bb + int(bh * 0.20)
        y_tor_bot = y_bb + int(bh * 0.45)
        ancho_tor_px = 0
        for yi in range(y_tor_top, min(y_tor_bot, img_h)):
            xs = np.where(mask[yi, :] > 0)[0]
            if len(xs) >= 2:
                ancho = int(xs[-1] - xs[0])
                if ancho > ancho_tor_px:
                    ancho_tor_px = ancho

        # Ancho de caderas: zona media 45-70% de la altura
        y_cad_top = y_bb + int(bh * 0.45)
        y_cad_bot = y_bb + int(bh * 0.70)
        ancho_cad_px = 0
        for yi in range(y_cad_top, min(y_cad_bot, img_h)):
            xs = np.where(mask[yi, :] > 0)[0]
            if len(xs) >= 2:
                ancho = int(xs[-1] - xs[0])
                if ancho > ancho_cad_px:
                    ancho_cad_px = ancho

        ratio_tor_cad   = ancho_tor_px / ancho_cad_px if ancho_cad_px > 0 else 1.0

        # Calcular escala propia de la foto trasera
        px_per_cm_trasera = bh / 123.0   # alto_bbox / alzada_ref Jersey
        ancho_tor_cm      = ancho_tor_px / px_per_cm_trasera if px_per_cm_trasera > 0 else 0
        pt_estimado       = ancho_tor_cm * np.pi

        print(f"        Roboflow conf : {confianza:.2f}")
        print(f"        Ancho tórax   : {ancho_tor_px} px  → {ancho_tor_cm:.1f} cm → PT={pt_estimado:.1f} cm")
        print(f"        Ancho caderas : {ancho_cad_px} px")
        print(f"        Alto bbox     : {bh} px  (px/cm={px_per_cm_trasera:.3f})")
        print(f"        Fill ratio    : {fill_ratio:.3f}")
        print(f"        Img trasera   : {img_w}×{img_h} px")
        if bh < 200:
            print(f"        ⚠ alto_bbox={bh}px muy pequeño — foto posiblemente recortada")
            print(f"          PT fiable requiere alto_bbox ≥ 250px (foto trasera completa)")

        # Guardar debug trasera con información de escala
        debug_tras = PROYECTO_DIR / f"debug_trasera_{Path(image_path).stem}.jpg"
        img_dbg = img.copy()
        overlay = img.copy()
        cv2.fillPoly(overlay, [points], (0, 200, 100))
        cv2.addWeighted(img_dbg, 0.6, overlay, 0.4, 0, img_dbg)
        cv2.polylines(img_dbg, [points], True, (0,255,100), 2)
        # Bounding box completo
        cv2.rectangle(img_dbg, (x_bb, y_bb), (x_bb+bw, y_bb+bh), (255,255,0), 1)
        # Línea ancho torácico
        y_mid_tor = (y_tor_top + y_tor_bot) // 2
        xs_tor = np.where(mask[min(y_mid_tor, img_h-1), :] > 0)[0]
        if len(xs_tor) >= 2:
            cv2.line(img_dbg, (xs_tor[0], y_mid_tor), (xs_tor[-1], y_mid_tor), (255,100,0), 3)
            cv2.putText(img_dbg, f"Tor:{ancho_tor_px}px={ancho_tor_cm:.0f}cm PT={pt_estimado:.0f}cm",
                        (xs_tor[0], y_mid_tor-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,100,0), 2)
        # Línea ancho cadera
        y_mid_cad = (y_cad_top + y_cad_bot) // 2
        xs_cad = np.where(mask[min(y_mid_cad, img_h-1), :] > 0)[0]
        if len(xs_cad) >= 2:
            cv2.line(img_dbg, (xs_cad[0], y_mid_cad), (xs_cad[-1], y_mid_cad), (100,0,255), 3)
            cv2.putText(img_dbg, f"Cad:{ancho_cad_px}px",
                        (xs_cad[0], y_mid_cad-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,0,255), 2)
        # Alto bbox — línea vertical para ver la escala
        cv2.line(img_dbg, (x_bb+bw+5, y_bb), (x_bb+bw+5, y_bb+bh), (0,255,255), 2)
        cv2.putText(img_dbg, f"H:{bh}px", (x_bb+bw+8, y_bb+bh//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 2)
        # Info escala en esquina
        color_ok = (60,220,60) if bh >= 200 else (0,100,255)
        cv2.putText(img_dbg, f"px/cm={px_per_cm_trasera:.2f}  {'OK' if bh>=200 else 'foto recortada'}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color_ok, 2)
        cv2.imwrite(str(debug_tras), img_dbg)
        print(f"        Debug trasera : {debug_tras.name}")

        return {
            "ancho_tor_px"  : ancho_tor_px,
            "ancho_cad_px"  : ancho_cad_px,
            "alto_px"       : bh,          # alto bbox trasera → escala propia
            "fill_ratio"    : round(fill_ratio, 4),
            "ratio_tor_cad" : round(ratio_tor_cad, 4),
            "confianza"     : round(confianza, 3),
            "img_w"         : img_w,
            "img_h"         : img_h,
            "_mask"         : mask,
        }

    except ImportError:
        print("        ⚠ inference-sdk no instalado → pip install inference-sdk")
        return {}
    except Exception as e:
        print(f"        ⚠ Roboflow error: {e}")
        return {}


def mejorar_pt_con_trasera(pt_lateral: float, datos_trasera: dict,
                            px_per_cm_lateral: float,
                            ac_ref_cm: float = AC_REF_DEFAULT) -> float:
    """
    Combina PT de vista lateral con ancho torácico de vista trasera.

    CORRECCIÓN CLAVE: usa la escala de la foto TRASERA (bh / ac_ref),
    no la escala lateral. Las dos fotos tienen diferente zoom/distancia.

    Escala trasera: px_per_cm_trasera = alto_bbox_trasera / alzada_ref
    Esto convierte correctamente ancho_tor_px a cm en esa foto específica.
    """
    if not datos_trasera or datos_trasera.get("ancho_tor_px", 0) == 0:
        return pt_lateral

    # Escala propia de la foto trasera — independiente de la lateral
    alto_px_trasera  = datos_trasera.get("alto_px", 0)
    if alto_px_trasera > 0:
        px_per_cm_trasera = alto_px_trasera / ac_ref_cm
    else:
        # Fallback: usar escala lateral solo si no hay dato trasero
        px_per_cm_trasera = px_per_cm_lateral

    ancho_tor_cm = datos_trasera["ancho_tor_px"] / px_per_cm_trasera

    # Tórax bovino Jersey ≈ elipse: circunferencia ≈ π × diámetro × factor_ovalado
    # Factor calibrado empíricamente: Jersey no es circular
    # PT_real = π × diámetro_real → factor_ovalado ≈ 1.0 si medimos bien el diámetro
    pt_trasera = float(np.clip(ancho_tor_cm * np.pi, 140.0, 210.0))

    confianza_rob = datos_trasera.get("confianza", 0.5)

    if confianza_rob >= 0.80:
        w_trasera = 0.60
    elif confianza_rob >= 0.60:
        w_trasera = 0.40
    else:
        w_trasera = 0.20

    pt_combinado = (pt_lateral * (1 - w_trasera)) + (pt_trasera * w_trasera)

    print(f"        px/cm lateral : {px_per_cm_lateral:.3f}  trasera: {px_per_cm_trasera:.3f}")
    print(f"        PT lateral    : {pt_lateral:.1f} cm")
    print(f"        PT trasera    : {pt_trasera:.1f} cm  "
          f"(ancho={ancho_tor_cm:.1f}cm, conf={confianza_rob:.2f})")
    print(f"        PT combinado  : {pt_combinado:.1f} cm  "
          f"(peso trasera={w_trasera:.0%})")

    return round(pt_combinado, 1)


# ══════════════════════════════════════════════════════════
# SAM — SEGMENTACIÓN MEJORADA
# ══════════════════════════════════════════════════════════

def segmentar_con_sam(image_bgr):
    import torch
    from segment_anything import sam_model_registry, SamPredictor

    h, w = image_bgr.shape[:2]
    print("        Cargando SAM (vit_b)...")
    sam    = sam_model_registry["vit_b"](checkpoint=str(SAM_MODEL))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam.to(device=device)
    predictor = SamPredictor(sam)
    predictor.set_image(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    print(f"        SAM listo  [{device}]")

    cx, cy = w // 2, h // 2
    fg_pts = np.array([
        [cx,          cy],
        [cx - w//8,   cy],
        [cx + w//8,   cy],
        [cx,          cy - h//8],
        [cx,          cy + h//10],
        [int(w*0.25), int(h*0.38)],   # zona torácica izquierda
        [int(w*0.75), int(h*0.38)],   # zona torácica derecha
        [cx,          int(h*0.35)],   # altura lomo
    ])
    bg_pts = np.array([
        [10,   10],   [w-10, 10],
        [10,   h-10], [w-10, h-10],
        [cx,   10],   [10,   cy],  [w-10, cy],
    ])

    all_pts = np.vstack([fg_pts, bg_pts])
    all_lbl = np.array([1]*len(fg_pts) + [0]*len(bg_pts))

    masks, scores, _ = predictor.predict(
        point_coords=all_pts, point_labels=all_lbl, multimask_output=True)

    mejor_score = -1
    mejor_mask  = None
    for mask, score in zip(masks, scores):
        fill = mask.sum() / (h * w)
        if 0.08 <= fill <= 0.80 and score > mejor_score:
            mejor_score = score
            mejor_mask  = mask
    if mejor_mask is None:
        mejor_mask = masks[np.argmax(scores)]

    print(f"        Score SAM : {mejor_score:.3f}  fill: {mejor_mask.sum()/(h*w)*100:.1f}%")

    mask_bin = mejor_mask.astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15,15))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return mask_bin, None
    main = max(cnts, key=cv2.contourArea)
    mc   = np.zeros_like(mask_bin)
    cv2.drawContours(mc, [main], -1, 255, -1)
    return mc, main


# ══════════════════════════════════════════════════════════
# DETECCIÓN DE ORIENTACIÓN
# ══════════════════════════════════════════════════════════

def detectar_orientacion(mask, x_bb, y_bb, bw, bh):
    y_top  = y_bb + int(bh * 0.05)
    y_mid  = y_bb + int(bh * 0.45)
    tercio = bw // 3

    def densidad(x0, x1):
        total = 0
        for xi in range(x0, min(x1, mask.shape[1])):
            total += int(np.sum(mask[y_top:y_mid, xi] > 0))
        return total / max(x1 - x0, 1)

    dens_izq = densidad(x_bb,            x_bb + tercio)
    dens_der = densidad(x_bb + 2*tercio, x_bb + bw)
    return "derecha" if dens_izq < dens_der else "izquierda"


# ══════════════════════════════════════════════════════════
# DETECCIÓN DEL LOMO
# ══════════════════════════════════════════════════════════

def _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado):
    y_ini  = y_bb + int(bh * 0.18)
    y_fin  = y_bb + int(bh * 0.60)
    min_px = int(bh * 0.10)
    margen_enc = int(bw * 0.25)
    margen_isq = int(bw * 0.19)

    if lado == "derecha":
        x_ini = x_bb + int(bw * 0.45)
        x_fin = x_bb + bw - margen_enc
        for xi in range(min(x_fin, mask.shape[1])-1, x_ini, -1):
            if len(np.where(mask[y_ini:y_fin, xi] > 0)[0]) >= min_px:
                return xi
        return x_bb + bw - margen_enc
    else:
        x_ini = x_bb + margen_isq
        x_fin = x_bb + int(bw * 0.50)
        for xi in range(x_ini, min(x_fin, mask.shape[1])):
            if len(np.where(mask[y_ini:y_fin, xi] > 0)[0]) >= min_px:
                return xi
        return x_bb + margen_isq


def detectar_lomo(mask, x_bb, y_bb, bw, bh, w_img):
    xs_validos, tops_raw = [], []
    for xi in range(x_bb, min(x_bb + bw, w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            xs_validos.append(xi)
            tops_raw.append(float(ys[0]))

    if len(xs_validos) < 20:
        return x_bb, x_bb + bw, tops_raw, xs_validos, "derecha"

    xs_arr   = np.array(xs_validos)
    tops_arr = np.array(tops_raw)
    win = max(len(xs_arr) // 10, 5)
    tops_smooth = np.array([
        np.median(tops_arr[max(0, i-win): i+win+1])
        for i in range(len(tops_arr))
    ])

    orientacion = detectar_orientacion(mask, x_bb, y_bb, bw, bh)
    mg          = int(len(xs_arr) * 0.10)
    zona_tops   = tops_smooth[mg: len(xs_arr)-mg]
    umbral      = np.percentile(zona_tops, 30)
    tol         = bh * 0.05

    en_lomo = tops_smooth <= (umbral + tol)
    en_lomo[:mg] = False
    en_lomo[len(xs_arr)-mg:] = False
    idx_lomo = np.where(en_lomo)[0]

    if len(idx_lomo) >= 5:
        gaps = np.where(np.diff(idx_lomo) > max(len(xs_arr)*0.05, 3))[0]
        bloques, prev = [], 0
        for g in gaps:
            bloques.append(idx_lomo[prev:g+1]); prev = g+1
        bloques.append(idx_lomo[prev:])
        bloque = max(bloques, key=len)  # noqa: F841

        if orientacion == "derecha":
            x_enc = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="derecha")
            x_isq = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="izquierda")
        else:
            x_enc = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="izquierda")
            x_isq = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="derecha")
    else:
        if orientacion == "derecha":
            x_enc = int(np.percentile(xs_arr, 22))
            x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78))
            x_isq = int(np.percentile(xs_arr, 22))

    if abs(x_isq - x_enc) < bw * 0.20:
        if orientacion == "derecha":
            x_enc = int(np.percentile(xs_arr, 22))
            x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78))
            x_isq = int(np.percentile(xs_arr, 22))

    return x_enc, x_isq, tops_smooth.tolist(), xs_validos, orientacion


# ══════════════════════════════════════════════════════════
# MEDIDAS ANATÓMICAS
# ══════════════════════════════════════════════════════════

def _seg(ys):
    if len(ys) < 2: return 0.0
    gaps = np.where(np.diff(ys) > 8)[0]
    if not len(gaps): return float(ys[-1]-ys[0])
    segs, p = [], 0
    for g in gaps:
        segs.append(ys[g]-ys[p]); p = g+1
    segs.append(ys[-1]-ys[p])
    return float(max(segs))


def get_alzada_ref(peso_estimado: float) -> float:
    for (lo, hi), ac in ALZADA_POR_RANGO.items():
        if lo <= peso_estimado < hi:
            return ac
    return AC_REF_DEFAULT


def medir(image, mask, contour, ac_ref_cm: float = AC_REF_DEFAULT):
    h_img, w_img = image.shape[:2]
    x_bb, y_bb, bw, bh = cv2.boundingRect(contour)

    max_h_px = 0.0
    x_ac = 0
    for xi in range(x_bb + int(bw*0.25), min(x_bb + int(bw*0.60), w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            h = float(ys[-1] - ys[0])
            if h > max_h_px:
                max_h_px = h; x_ac = xi
    if max_h_px < bh * 0.35:
        max_h_px = float(bh); x_ac = x_bb + bw // 2

    px = max_h_px / ac_ref_cm

    x_enc, x_isq, tops_smooth, xs_validos, orientacion = detectar_lomo(
        mask, x_bb, y_bb, bw, bh, w_img)

    lc_px  = max(abs(x_isq - x_enc), 1)
    x_izq  = min(x_enc, x_isq)
    x_der  = max(x_enc, x_isq)

    # LC corregida con factor dinámico calibrado por rango de lc_img
    # Factor varía: ~2.5 cuando SAM midió poco (lc_img bajo)
    #               ~1.1 cuando SAM midió bien (lc_img alto como en la imagen debug)
    lc_cm_raw   = (lc_px / px) + 20
    lc_factor   = get_lc_factor(lc_cm_raw)
    lc_cm       = lc_cm_raw * lc_factor

    # ── x_pt — posición del perímetro torácico ───────────────────
    # El PT se mide DETRÁS DEL MIEMBRO ANTERIOR.
    # La lógica depende de la orientación de la cabeza:
    #   orientacion="derecha"  → cabeza a la derecha  → miembro ant. en x_der
    #   orientacion="izquierda"→ cabeza a la izquierda → miembro ant. en x_izq
    # En ambos casos: PT = 22% desde el extremo donde está la CABEZA
    if orientacion == "derecha":
        # Cabeza a la derecha → miembro anterior cerca de x_der
        x_pt_base = np.clip(x_der - int(lc_px * 0.22), 0, w_img-1)
    else:
        # Cabeza a la izquierda → miembro anterior cerca de x_izq
        x_pt_base = np.clip(x_izq + int(lc_px * 0.22), 0, w_img-1)

    y_tor_top = y_bb + int(bh * 0.05)
    y_tor_bot = y_bb + int(bh * 0.46)

    h_tor_max = 0.0
    x_pt_best = x_pt_base
    for xi in range(
        max(0, x_pt_base - int(lc_px * 0.05)),
        min(w_img, x_pt_base + int(lc_px * 0.05))
    ):
        ys_i  = np.where(mask[:, xi] > 0)[0]
        ys_ti = ys_i[(ys_i >= y_tor_top) & (ys_i <= y_tor_bot)]
        if len(ys_ti) >= 2:
            h_i = float(ys_ti[-1] - ys_ti[0])
            if h_i > h_tor_max:
                h_tor_max = h_i; x_pt_best = xi

    if h_tor_max == 0.0:
        ys_pt  = np.where(mask[:, x_pt_base] > 0)[0]
        ys_tor = ys_pt[(ys_pt >= y_tor_top) & (ys_pt <= y_tor_bot)]
        h_tor_max = float(ys_tor[-1]-ys_tor[0]) if len(ys_tor)>=2 else _seg(ys_pt)

    pt_cm = (h_tor_max * np.pi) / px
    x_pt  = x_pt_best

    # Alzada a la grupa
    ys_ag = np.where(mask[:, x_isq] > 0)[0]
    ag_px = float(ys_ag[-1]-ys_ag[0]) if len(ys_ag)>=2 else max_h_px
    ag_cm = ag_px / px

    # Cadera
    x_cad  = np.clip(x_izq + int(lc_px*0.80), 0, w_img-1)
    y_fs   = y_bb + int(bh * 0.05)
    y_fi   = y_bb + int(bh * 0.58)
    ys_c   = np.where(mask[:, x_cad] > 0)[0]
    ys_ct  = ys_c[(ys_c >= y_fs) & (ys_c <= y_fi)]
    cad_cm = (float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else _seg(ys_c)) / px

    area  = float(cv2.contourArea(contour))
    perim = float(cv2.arcLength(contour, True))
    htor_norm = h_tor_max / max_h_px if max_h_px > 0 else 0.0
    cad_h_px  = float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else 0.0
    cad_norm  = cad_h_px / max_h_px if max_h_px > 0 else 0.0

    # Rectángulo mínimo orientado — Nixon & Aguado (2012)
    rect_min                    = cv2.minAreaRect(contour)
    box_min                     = np.int32(cv2.boxPoints(rect_min))
    (cx_r, cy_r), (w_r, h_r), angulo_r = rect_min
    largo_min  = float(max(w_r, h_r))
    alto_min   = float(min(w_r, h_r))
    ratio_lh_min  = round(largo_min / alto_min, 4) if alto_min > 0 else 1.0
    area_minrect  = largo_min * alto_min
    ratio_lh_final   = ratio_lh_min if abs(angulo_r) > 2.0 else round(lc_px / max_h_px if max_h_px > 0 else 1, 4)
    area_norm_final  = round(area / area_minrect, 5) if area_minrect > 0 else round(area / (w_img*h_img), 5)

    return {
        "lc":          round(lc_cm, 1),
        "lc_raw":      round(lc_cm_raw, 1),
        "lc_factor":   round(lc_factor, 3),
        "ac":          round(max_h_px / px, 1),
        "ag":          round(ag_cm, 1),
        "pt":          round(pt_cm, 1),
        "cadera":      round(cad_cm, 1),
        "area_norm":   area_norm_final,
        "ratio_lh":    ratio_lh_final,
        "perim_norm":  round(perim / max_h_px if max_h_px > 0 else 1, 4),
        "htor_norm":   round(htor_norm, 4),
        "cad_norm":    round(cad_norm, 4),
        "px_per_cm":   round(px, 4),
        "ac_ref_cm":   ac_ref_cm,
        "angulo_r":    round(angulo_r, 2),
        "confidence":  round(min(area / float(bw*bh), 1.0) if bw*bh > 0 else 0, 3),
        "x_bb":x_bb, "y_bb":y_bb, "bw":bw, "bh":bh,
        "x_enc":x_enc, "x_isq":x_isq, "x_pt":x_pt, "x_cad":x_cad, "x_ac":x_ac,
        "max_h_px":max_h_px, "y_fs":y_fs, "y_fi":y_fi,
        "orientacion": orientacion,
        "_tops_smooth": tops_smooth, "_xs_validos": xs_validos,
        "_box_min":     box_min,
    }


# ══════════════════════════════════════════════════════════
# DEBUG VISUAL
# ══════════════════════════════════════════════════════════

def guardar_debug(image, mask, contour, m, path):
    ov  = image.copy()
    col = np.zeros_like(image)
    col[mask > 0] = [30, 200, 80]
    cv2.addWeighted(col, 0.30, ov, 0.70, 0, ov)
    cv2.drawContours(ov, [contour], -1, (40,255,120), 2)

    if "_box_min" in m:
        cv2.drawContours(ov, [m["_box_min"]], 0, (255,255,255), 1)
        cv2.putText(ov, f"minRect {m.get('angulo_r',0):.1f}°",
                    (m["x_bb"]+5, m["y_bb"]-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

    x_enc=m["x_enc"]; x_isq=m["x_isq"]
    x_pt=m["x_pt"];   x_cad=m["x_cad"]
    x_ac_col=m.get("x_ac", x_enc+int((m["x_isq"]-m["x_enc"])*0.38))
    y_bb=m["y_bb"];   bh=m["bh"]
    px=m["px_per_cm"]; hpx=m["max_h_px"]
    y_fs=m["y_fs"];   y_fi=m["y_fi"]
    h_img, w_img = ov.shape[:2]

    tops   = m.get("_tops_smooth",[])
    xs_val = m.get("_xs_validos",[])
    if len(tops)==len(xs_val) and len(tops)>1:
        pts = [(int(xs_val[i]),int(tops[i])) for i in range(len(tops))]
        for i in range(len(pts)-1):
            cv2.line(ov, pts[i], pts[i+1], (0,220,255), 1)

    cv2.rectangle(ov,(x_enc,y_fs),(x_isq,y_fi),(100,100,255),1)
    ay = min(y_fi+28, h_img-40)
    cv2.arrowedLine(ov,(x_enc,ay),(x_isq,ay),(0,210,255),2,tipLength=0.02)
    cv2.arrowedLine(ov,(x_isq,ay),(x_enc,ay),(0,210,255),2,tipLength=0.02)
    cv2.putText(ov,f"LC:{m['lc']:.0f}cm (raw:{m['lc_raw']:.0f})",
                (x_enc+(x_isq-x_enc)//2-80,ay+24),
                cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,210,255),2)

    ys_enc    = np.where(mask[:,np.clip(x_enc,0,w_img-1)]>0)[0]
    y_enc_top = int(ys_enc[0]) if len(ys_enc)>0 else y_fs
    cv2.circle(ov,(x_enc,y_enc_top),10,(0,255,255),-1)
    cv2.putText(ov,"ENCUENTRO",(x_enc-5,y_enc_top-12),
                cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,255,255),2)

    ys_isq    = np.where(mask[:,np.clip(x_isq,0,w_img-1)]>0)[0]
    y_isq_top = int(ys_isq[0]) if len(ys_isq)>0 else y_fs
    cv2.circle(ov,(x_isq,y_isq_top),10,(0,255,255),-1)
    cv2.putText(ov,"ISQUION",(x_isq-75,y_isq_top-12),
                cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,255,255),2)

    ys_ac    = np.where(mask[:,np.clip(x_ac_col,0,w_img-1)]>0)[0]
    y_ac_top = int(ys_ac[0])  if len(ys_ac)>0 else y_bb
    y_ac_bot = int(ys_ac[-1]) if len(ys_ac)>0 else y_bb+int(hpx)
    cv2.line(ov,(x_ac_col,y_ac_top),(x_ac_col,y_ac_bot),(255,120,30),2)
    cv2.putText(ov,f"AC:{m['ac']:.0f}cm (ref:{m['ac_ref_cm']:.0f})",
                (x_ac_col+6,y_ac_top+int((y_ac_bot-y_ac_top)*0.45)),
                cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,120,30),2)

    ys_ag    = np.where(mask[:,np.clip(x_isq,0,w_img-1)]>0)[0]
    y_ag_top = int(ys_ag[0])  if len(ys_ag)>0 else y_isq_top
    y_ag_bot = int(ys_ag[-1]) if len(ys_ag)>0 else y_bb+int(hpx)
    cv2.line(ov,(x_isq,y_ag_top),(x_isq,y_ag_bot),(0,200,150),2)

    cv2.line(ov,(x_pt,y_fs),(x_pt,y_fi),(255,60,200),2)
    cv2.putText(ov,f"PT:{m['pt']:.0f}cm",
                (x_pt+5,y_fs+int((y_fi-y_fs)*0.35)),
                cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,60,200),2)

    cv2.line(ov,(x_cad,y_fs),(x_cad,y_fi),(180,80,255),2)
    cv2.putText(ov,"CAD",(x_cad+4,y_fs+18),cv2.FONT_HERSHEY_SIMPLEX,0.4,(180,80,255),1)

    lc_ok = 120<=m["lc"]<=200; pt_ok = 140<=m["pt"]<=210
    c = (60,220,60) if (lc_ok and pt_ok) else (0,100,255)
    cv2.putText(ov,
        f"LC:{m['lc']}cm {'OK' if lc_ok else 'REV'}  "
        f"PT:{m['pt']}cm {'OK' if pt_ok else 'REV'}  [{m.get('orientacion','?')}]",
        (10,28),cv2.FONT_HERSHEY_SIMPLEX,0.50,c,2)

    h,w = image.shape[:2]
    cx,cy = w//2,h//2
    for pt in [(cx,cy),(cx-w//8,cy),(cx+w//8,cy),(cx,cy-h//8),(cx,cy+h//10),
               (int(w*0.25),int(h*0.38)),(int(w*0.75),int(h*0.38))]:
        cv2.circle(ov,pt,5,(0,255,0),-1)
    for pt in [(10,10),(w-10,10),(10,h-10),(w-10,h-10),(cx,10),(10,cy),(w-10,cy)]:
        cv2.circle(ov,pt,5,(0,0,255),-1)

    cv2.imwrite(str(path), ov)


# ══════════════════════════════════════════════════════════
# FÓRMULA Y CONVERSIÓN
# ══════════════════════════════════════════════════════════

def calcular_peso_formula(pt, lc, bcs):
    PT_FACTOR = 0.838; LC_FACTOR = 0.766; BASE_K = 10999.0
    pt_corr = float(np.clip(pt * PT_FACTOR, 148.0, 198.0))
    lc_corr = float(np.clip(lc * LC_FACTOR, 108.0, 148.0))
    if bcs >= 4.0: BASE_K -= 250
    if bcs <= 2.5: BASE_K += 250
    return round((pt_corr**2 * lc_corr) / BASE_K, 1)


# Mediana de pt_real por BCS — calibrado con 67 vacas Jersey
BCS_PT_ANCHOR = {3.00: 179.0, 3.25: 178.0, 3.50: 181.0, 4.00: 189.0, 4.50: 197.0}
PT_IMG_MEDIAN = 185.0    # mediana pt_img del dataset
PT_IMG_ESCALA = 0.338    # std(pt_real) / std(pt_img) — cuánto ajustar pt_img

# Rangos fisiológicos de peso por BCS Jersey (calibrado con 67 vacas)
PESO_RANGO_BCS = {
    3.00: (303, 520),
    3.25: (340, 530),
    3.50: (360, 560),
    4.00: (390, 640),
    4.50: (430, 702),
}


def estimar_cinta_desde_sam(pt_img: float, lc_img: float, bcs: float = 3.0):
    """
    Estima pt_real y lc_real desde medidas SAM.

    pt_real: anclado a la mediana de PT por BCS, ajustado con pt_img.
             Más preciso que regresión lineal porque BCS correlaciona
             con pt_real (r=0.44) mientras que pt_img no (r=0.08).
    lc_real: 160 cm (mediana dataset — lc_img no aporta señal útil).
    """
    anchor = BCS_PT_ANCHOR.get(round(bcs * 4) / 4, 180.0)  # redondear a .00/.25/.50/.75
    pt_real = anchor + (pt_img - PT_IMG_MEDIAN) * PT_IMG_ESCALA
    pt_real = float(np.clip(pt_real, 155.0, 205.0))
    lc_real = 160.0
    return pt_real, lc_real


def clamp_peso_por_bcs(peso: float, bcs: float) -> float:
    """
    Aplica clamp fisiológico al peso según BCS.
    Evita predicciones fuera del rango biológicamente posible para Jersey.
    Ejemplo: BCS 3.0 no puede dar 540 kg (máximo fisiológico ~520 kg).
    """
    bcs_key = round(bcs * 4) / 4
    lo, hi  = PESO_RANGO_BCS.get(bcs_key, (280, 720))
    clamped = float(np.clip(peso, lo, hi))
    if clamped != peso:
        print(f"        ⚠ Clamp BCS {bcs}: {peso:.1f} → {clamped:.1f} kg  "
              f"(rango fisiológico {lo}–{hi} kg)")
    return clamped


# ══════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════

with open(args.lateral,"rb") as f: lat_b = f.read()
with open(args.trasera,"rb") as f: tra_b = f.read()
print(f"[ 1/5 ] Cargadas  lateral:{len(lat_b)/1024:.0f}KB | trasera:{len(tra_b)/1024:.0f}KB\n")

# ── ROBOFLOW — vista trasera ──────────────────────────────────────
datos_trasera = {}
if not args.sin_roboflow:
    print("[ 2/5 ] Roboflow → segmentación trasera...")
    t0 = time.time()
    datos_trasera = segmentar_trasera_roboflow(args.trasera)
    print(f"        {time.time()-t0:.2f}s\n")
else:
    print("[ 2/5 ] Roboflow omitido (--sin-roboflow)\n")

# ── BCS ───────────────────────────────────────────────────────────
bcs_score = args.bcs; bcs_conf = 1.0
if bcs_score is None:
    print("[ 3/5 ] Prediciendo BCS (foto trasera)...")
    t0 = time.time()
    try:
        from ultralytics import YOLO
        res      = YOLO(str(BCS_MODEL))(args.trasera, verbose=False)
        probs    = res[0].probs
        top_idx  = int(probs.top1)
        bcs_conf = float(probs.top1conf.item())
        nombres  = res[0].names
        try:    bcs_score = float(nombres[top_idx])
        except: bcs_score = {0:3.0,1:3.25,2:3.5,3:4.0,4:4.5}.get(top_idx,3.0)
        print(f"        BCS:{bcs_score}  Conf:{bcs_conf*100:.1f}%")
        for i in range(len(nombres)):
            p = float(probs.data[i].item())*100
            print(f"          BCS {float(nombres[i]):<5} {'█'*int(p/5)} {p:.1f}%")
    except Exception as e:
        print(f"        ⚠ {e} → BCS=3.0"); bcs_score, bcs_conf = 3.0, 0.0
    print(f"        {time.time()-t0:.2f}s\n")
else:
    print(f"[ 3/5 ] BCS manual: {bcs_score}\n")

# ── SAM + MEDIDAS LATERALES ───────────────────────────────────────
print("[ 4/5 ] SAM → silueta  |  OpenCV → medidas...")
t1 = time.time()
try:
    nparr = np.frombuffer(lat_b, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h0,w0 = img.shape[:2]
    if max(h0,w0) > 1280:
        f   = 1280/max(h0,w0)
        img = cv2.resize(img,(int(w0*f),int(h0*f)))

    mask, contour = segmentar_con_sam(img)
    if contour is None:
        raise ValueError("SAM no generó contorno válido")

    m = medir(img, mask, contour, ac_ref_cm=AC_REF_DEFAULT)
    print(f"        [1ª pasada] LC:{m['lc']}cm (raw:{m['lc_raw']}) PT:{m['pt']}cm")
    print(f"        AC:{m['ac']}cm  ángulo:{m['angulo_r']:.1f}°  Conf:{m['confidence']*100:.0f}%")
    print(f"        {time.time()-t1:.2f}s\n")

    debug_path = PROYECTO_DIR / f"debug_{Path(args.lateral).stem}.jpg"
    guardar_debug(img, mask, contour, m, debug_path)

except Exception as e:
    print(f"\n❌ Error SAM: {e}\n")
    import traceback; traceback.print_exc(); sys.exit(1)

# ── ESTIMACIÓN ────────────────────────────────────────────────────
print("[ 5/5 ] Estimando peso (XGBoost + Fórmula)...")
t2 = time.time()
try:
    pt = m["pt"]
    lc = m["lc"]

    # Fix 3: corregir ratio_lh cuando SAM detecta la vaca vertical (ángulo >45°)
    # En ese caso largo/corto está invertido respecto al modelo
    ratio_lh_corr = m["ratio_lh"]
    if abs(m["angulo_r"]) > 45:
        ratio_lh_corr = round(1.0 / m["ratio_lh"], 4) if m["ratio_lh"] > 0 else 1.0
        print(f"        ⚠ ángulo={m['angulo_r']:.0f}° → ratio_lh corregido {m['ratio_lh']:.3f}→{ratio_lh_corr:.3f}")

    lc_ok = 120<=lc<=200; pt_ok = 140<=pt<=210

    # Schaeffer con BCS anchor — respaldo si XGBoost falla
    BCS_PT_ANCHOR_F = {3.00:179.0, 3.25:178.0, 3.50:181.0, 4.00:189.0, 4.50:197.0}
    anchor  = BCS_PT_ANCHOR_F.get(round(bcs_score*4)/4, 180.0)
    K_bcs   = 10999.0
    peso_schaeffer_bcs = round((anchor**2 * 160.0) / K_bcs, 1)

    PESO_MIN_KG = 200.0; PESO_MAX_KG = 750.0
    peso_xgboost = None

    try:
        import xgboost as xgb
        if MASS_MODEL.exists():
            b = xgb.Booster(); b.load_model(str(MASS_MODEL))
            if b.num_features() != len(FEATURE_NAMES):
                raise ValueError(f"modelo desactualizado ({b.num_features()} features)")
            pt_real, lc_real = estimar_cinta_desde_sam(pt, lc, bcs_score)
            vol_img  = (pt**2)      * lc
            vol_real = (pt_real**2) * lc_real
            feat = np.array([[
                ratio_lh_corr, m["htor_norm"], m["cad_norm"],   # ← ratio corregido
                m["perim_norm"], m["area_norm"],
                bcs_score, pt, lc, vol_img, pt_real, lc_real, vol_real,
            ]], dtype=np.float32)
            pred = float(b.predict(xgb.DMatrix(feat))[0])
            if PESO_MIN_KG <= pred <= PESO_MAX_KG:
                peso_xgboost = pred
                print(f"        XGBoost: {pred:.1f} kg")
            else:
                print(f"        ⚠ XGBoost fuera de rango ({pred:.1f}kg) → usando Schaeffer BCS")
    except Exception as e_xgb:
        print(f"        ⚠ XGBoost: {e_xgb}")

    # Fix 1+2: solo XGBoost sin blend con fórmula, sin clamp
    # La fórmula Schaeffer con PT=160cm da 200-300kg siempre → contamina el blend
    # El clamp bloqueaba vacas pesadas (V8,V66,V11) en 390 kg
    if peso_xgboost is not None:
        masa_kg   = peso_xgboost
        blend_str = "solo XGBoost"
        xgb_str   = f"{peso_xgboost:.1f} kg"
    else:
        masa_kg   = peso_schaeffer_bcs
        xgb_str   = "fallback"
        blend_str = f"Schaeffer BCS (anchor={anchor:.0f}cm)"
        print(f"        Schaeffer BCS: {masa_kg:.1f} kg")

    margen     = round(masa_kg * 0.05, 1)
    conf_total = m["confidence"] * 0.6 + bcs_conf * 0.4
    print(f"\n        Peso Final: {masa_kg:.1f} kg  (± {margen} kg)  [{blend_str}]")
    print(f"        {time.time()-t2:.2f}s\n")

except Exception as e:
    print(f"\n❌ Error estimación: {e}\n")
    import traceback; traceback.print_exc(); sys.exit(1)

lc_ok = 120<=m["lc"]<=200; pt_ok = 140<=m["pt"]<=210
bcs_desc = {3.0:"Moderado",3.25:"Moderado-bueno",3.5:"Bueno",
            4.0:"Óptimo",4.5:"Muy bueno"}.get(bcs_score,"—")

print(SEP)
print("  RESULTADO FINAL")
print(SEP)
print(f"  Peso estimado    : {masa_kg:.1f} kg  (± {margen} kg)")
print(f"    · Fórmula      : {peso_formula:.1f} kg")
print(f"    · XGBoost      : {xgb_str}")
print(f"    · Blend        : {blend_str}")
print(f"  BCS predicho     : {bcs_score}  — {bcs_desc}")
print(f"  Confianza total  : {conf_total*100:.0f}%")
print(SEP)
print("  MORFOMETRÍA")
print(SEP)
print(f"  Largo corporal   : {m['lc']} cm  {'✓' if lc_ok else '⚠'}  (raw:{m['lc_raw']} ×{m['lc_factor']})")
print(f"  LC proyectada    : {m['lc_raw']} cm")
print(f"  Altura a la cruz : {m['ac']} cm  (ref={m['ac_ref_cm']} cm)")
print(f"  Perímetro torác. : {pt:.1f} cm  {'✓' if pt_ok else '⚠'}")
print(f"  Ancho de cadera  : {m['cadera']} cm")
print(f"  ratio_lh         : {m['ratio_lh']:.4f}  (ángulo={m.get('angulo_r',0):.1f}°)")
print(f"  Escala (px/cm)   : {m['px_per_cm']:.3f}")
print(f"  Segmentación SAM : {m['confidence']*100:.0f}%")
if datos_trasera:
    print(f"\n  Vista trasera (Roboflow):")
    print(f"  Ancho tórax      : {datos_trasera.get('ancho_tor_px',0)} px")
    print(f"  Ancho caderas    : {datos_trasera.get('ancho_cad_px',0)} px")
    print(f"  Fill ratio       : {datos_trasera.get('fill_ratio',0):.3f}")
    print(f"  ratio_tor_cad    : {datos_trasera.get('ratio_tor_cad',0):.3f}")
if not lc_ok or not pt_ok:
    print(f"\n  ⚠ Medidas fuera del rango esperado Jersey")
print(SEP)
print(f"\n  Debug lateral : {debug_path.name}")
if datos_trasera:
    print(f"  Debug trasera : debug_trasera_{Path(args.trasera).stem}.jpg")
print(SEP + "\n")