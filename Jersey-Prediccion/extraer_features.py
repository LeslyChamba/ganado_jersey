# extraer_features.py
"""
BovineAI — Extracción de features para reentrenamiento XGBoost
Versión 2: usa medidas físicas reales (LC, PT, AC) del CSV para calibrar
la escala por imagen y como features directas, eliminando el error de
estimación de PT desde vista lateral.

Estructura esperada de carpetas:
  FOTOS_DIR/
    V1/  imagen_001.jpg  imagen_002.jpg ...
    V2/  imagen_001.jpg  ...

CSV de medidas físicas (medidas_fisicas.csv):
  vaca_id;lc_real;pt_real;ac_real;peso_real;bcs
  V1;148.0;172.5;123.0;320.5;3.25
  V2;155.0;180.0;125.0;415.0;3.50

Uso:
  python extraer_features.py
  python extraer_features.py --fotos_dir C:/mis/fotos --medidas medidas_fisicas.csv
"""

import argparse
import re
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

# ── Rutas ─────────────────────────────────────────────────────────────────────
PROYECTO_DIR      = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
SAM_MODEL         = PROYECTO_DIR / "models_pt" / "sam_vit_b.pth"
FOTOS_DIR_DEFAULT = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\Dataset-Vacas\V1")  # Cambia a tu carpeta de fotos
MEDIDAS_DEFAULT   = PROYECTO_DIR / "pesos_vacas_PLANTILLA.csv"
SALIDA_DEFAULT    = PROYECTO_DIR / "features_imagenes.csv"
EXTENSIONES       = {".jpg", ".jpeg", ".png", ".bmp"}

parser = argparse.ArgumentParser()
parser.add_argument("--fotos_dir", default=str(FOTOS_DIR_DEFAULT))
parser.add_argument("--medidas",   default=str(MEDIDAS_DEFAULT))
parser.add_argument("--salida",    default=str(SALIDA_DEFAULT))
parser.add_argument("--max_dim",      type=int, default=1280)
parser.add_argument("--max_por_vaca", type=int, default=20,
                    help="Máximo de imágenes a procesar por vaca (0=todas)")
args = parser.parse_args()

FOTOS_DIR = Path(args.fotos_dir)
SALIDA    = Path(args.salida)

SEP = "═" * 62
print(f"\n{SEP}")
print("  BovineAI — Extracción de features v2 (con medidas reales)")
print(f"{SEP}")
print(f"  Fotos dir : {FOTOS_DIR}")
print(f"  Medidas   : {args.medidas}")
print(f"  Salida    : {SALIDA}")
print(f"{SEP}\n")

if not SAM_MODEL.exists():
    print(f"❌ SAM no encontrado: {SAM_MODEL}"); raise SystemExit(1)


# ══════════════════════════════════════════════════════════
# CARGAR MEDIDAS FÍSICAS REALES
# ══════════════════════════════════════════════════════════

medidas_path = Path(args.medidas)
if not medidas_path.exists():
    print(f"❌ Archivo de medidas no encontrado: {medidas_path}")
    print("   Crea medidas_fisicas.csv con columnas:")
    print("   vaca_id;lc_real;pt_real;ac_real;peso_real;bcs")
    raise SystemExit(1)

# Leer CSV normalizando separadores decimales automáticamente
import io as _io
medidas_df = None

# Leer como texto y normalizar: reemplazar comas decimales por puntos
# (coma decimal: número seguido de coma seguido de dígito, ej: 3,5 → 3.5)
raw_text = medidas_path.read_text(encoding="utf-8-sig")

# Detectar separador de columnas
sep = ";" if raw_text.count(";") >= 3 else ","

# Si el separador es ";" entonces las comas son decimales → reemplazarlas
if sep == ";":
    import re as _re
    # Reemplaza comas entre dígitos (decimales) por puntos
    raw_text_norm = _re.sub(r"(?<=\d),(?=\d)", ".", raw_text)
else:
    raw_text_norm = raw_text

try:
    medidas_df = pd.read_csv(_io.StringIO(raw_text_norm), sep=sep, decimal=".")
    for col in ["pt_real", "lc_real", "peso_real", "bcs"]:
        if col in medidas_df.columns:
            medidas_df[col] = pd.to_numeric(medidas_df[col], errors="coerce")
    n_validos = medidas_df["peso_real"].notna().sum() if "peso_real" in medidas_df.columns else 0
    print(f"  CSV leído: sep='{sep}' → {n_validos} filas válidas")
except Exception as e:
    print(f"  ❌ Error leyendo CSV: {e}")

if medidas_df is None:
    print("❌ No se pudo leer medidas_fisicas.csv")
    print("   Asegúrate de que tenga: vaca_id;lc_real;pt_real;ac_real;peso_real;bcs")
    raise SystemExit(1)

# Convertir a numérico
for col in ["lc_real", "pt_real", "ac_real", "peso_real", "bcs"]:
    if col in medidas_df.columns:
        medidas_df[col] = pd.to_numeric(medidas_df[col], errors="coerce")

medidas_dict = medidas_df.set_index("vaca_id").to_dict("index")
print(f"  Medidas reales cargadas: {len(medidas_dict)} vacas")
print(f"  Columnas disponibles   : {list(medidas_df.columns)}")

# Verificar columnas obligatorias
tiene_lc  = "lc_real"  in medidas_df.columns
tiene_pt  = "pt_real"  in medidas_df.columns
tiene_ac  = "ac_real"  in medidas_df.columns

# Sin AC real → escala con 123 cm estándar Jersey (aceptable)
if tiene_ac:
    print("  ✓ AC real disponible → escala px/cm calibrada por vaca")
else:
    print("  ℹ AC real no disponible → escala estándar Jersey 123 cm (OK)")
if tiene_lc and tiene_pt:
    print("  ✓ LC y PT reales disponibles → features directas")
print()
print()


# ══════════════════════════════════════════════════════════
# DESCUBRIR IMÁGENES
# ══════════════════════════════════════════════════════════

def extraer_vaca_id(nombre: str) -> str:
    """
    Convierte el nombre de carpeta/archivo al vaca_id del CSV.
    Ejemplos:
      "V1 (23)"  → "V1"
      "V1(23)"   → "V1"
      "V10 (5)"  → "V10"
      "V23"      → "V23"
      "V3 (210)" → "V3"
    """
    # Quitar cualquier sufijo " (N)" o "(N)" al final
    limpio = re.sub(r"\s*\(\d+\)\s*$", "", nombre).strip()
    return limpio if limpio else nombre


def descubrir_imagenes(base: Path):
    registros = []
    subdirs   = [d for d in base.iterdir() if d.is_dir()]
    if subdirs:
        for subdir in sorted(subdirs):
            vaca_id = extraer_vaca_id(subdir.name)
            imgs    = sorted([f for f in subdir.iterdir()
                               if f.suffix.lower() in EXTENSIONES])
            for img in imgs:
                registros.append((vaca_id, img))
    else:
        for img in sorted(base.iterdir()):
            if img.suffix.lower() not in EXTENSIONES: continue
            vaca_id = extraer_vaca_id(img.stem)
            registros.append((vaca_id, img))
    return registros

registros    = descubrir_imagenes(FOTOS_DIR)
vacas_unicas = sorted({v for v, _ in registros})
print(f"  Imágenes encontradas : {len(registros)}")
print(f"  Vacas únicas         : {len(vacas_unicas)}")

# Filtrar solo vacas que tienen medidas reales
registros_validos = [(v, p) for v, p in registros if v in medidas_dict]
vacas_sin_medidas = set(vacas_unicas) - set(medidas_dict.keys())
if vacas_sin_medidas:
    print(f"  ⚠ Vacas SIN medidas reales (omitidas): {sorted(vacas_sin_medidas)}")

# Muestreo por vaca: tomar imágenes distribuidas uniformemente
if args.max_por_vaca > 0:
    import random
    random.seed(42)
    from collections import defaultdict
    por_vaca = defaultdict(list)
    for v, p in registros_validos:
        por_vaca[v].append(p)
    registros_validos = []
    for v in sorted(por_vaca):
        imgs = sorted(por_vaca[v])
        if len(imgs) <= args.max_por_vaca:
            seleccion = imgs
        else:
            # Distribuir uniformemente a lo largo de la lista
            paso = len(imgs) / args.max_por_vaca
            seleccion = [imgs[int(i * paso)] for i in range(args.max_por_vaca)]
        registros_validos.extend([(v, p) for p in seleccion])
    print(f"  Muestreo            : {args.max_por_vaca} imgs/vaca máx → {len(registros_validos)} imágenes totales")
else:
    print(f"  Muestreo            : TODAS las imágenes")

print(f"  Imágenes a procesar  : {len(registros_validos)}\n")

if not registros_validos:
    print("❌ Ninguna vaca tiene medidas reales. Revisa medidas_fisicas.csv")
    raise SystemExit(1)


# ══════════════════════════════════════════════════════════
# SAM — carga única
# ══════════════════════════════════════════════════════════

import torch
from segment_anything import sam_model_registry, SamPredictor

print("  Cargando SAM (vit_b)...")
sam       = sam_model_registry["vit_b"](checkpoint=str(SAM_MODEL))
device    = "cuda" if torch.cuda.is_available() else "cpu"
sam.to(device=device)
predictor = SamPredictor(sam)
print(f"  SAM listo [{device}]\n")


# ══════════════════════════════════════════════════════════
# FUNCIONES
# ══════════════════════════════════════════════════════════

def segmentar(image_bgr):
    h, w = image_bgr.shape[:2]
    predictor.set_image(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    cx, cy = w // 2, h // 2

    fg_pts = np.array([[cx, cy], [cx-w//8, cy], [cx+w//8, cy],
                        [cx, cy-h//8], [cx, cy+h//10]])
    bg_pts = np.array([[10,10],[w-10,10],[10,h-10],[w-10,h-10],
                        [cx,10],[10,cy],[w-10,cy]])
    all_pts = np.vstack([fg_pts, bg_pts])
    all_lbl = np.array([1]*5 + [0]*7)

    masks, scores, _ = predictor.predict(
        point_coords=all_pts, point_labels=all_lbl, multimask_output=True)

    mejor_mask, mejor_score = None, -1
    for mask, score in zip(masks, scores):
        fill = mask.sum() / (h * w)
        if 0.08 <= fill <= 0.80 and score > mejor_score:
            mejor_score = score; mejor_mask = mask
    if mejor_mask is None:
        mejor_mask = masks[np.argmax(scores)]

    mask_bin = mejor_mask.astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15,15))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts: return None, None, mejor_score
    main = max(cnts, key=cv2.contourArea)
    mc = np.zeros_like(mask_bin)
    cv2.drawContours(mc, [main], -1, 255, -1)
    return mc, main, float(mejor_score)


def detectar_lomo(mask, x_bb, y_bb, bw, bh, w_img):
    xs_v, tops = [], []
    for xi in range(x_bb, min(x_bb+bw, w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            xs_v.append(xi); tops.append(float(ys[0]))
    if len(xs_v) < 20:
        return x_bb, x_bb+bw

    xs_arr = np.array(xs_v); tops_arr = np.array(tops)
    win = max(len(xs_arr)//12, 5)
    tops_s = np.array([np.median(tops_arr[max(0,i-win):i+win+1])
                       for i in range(len(tops_arr))])
    mi = int(len(xs_arr)*0.15); md = int(len(xs_arr)*0.10)
    zona = tops_s[mi:len(xs_arr)-md]
    umbral = np.percentile(zona, 25)
    en_lomo = tops_s <= (umbral + bh*0.04)
    en_lomo[:mi] = False; en_lomo[len(xs_arr)-md:] = False
    idx = np.where(en_lomo)[0]

    if len(idx) >= 5:
        gaps = np.where(np.diff(idx) > max(len(xs_arr)*0.05, 3))[0]
        bloques, p = [], 0
        for g in gaps: bloques.append(idx[p:g+1]); p = g+1
        bloques.append(idx[p:])
        b = max(bloques, key=len)
        return int(xs_arr[b[0]]), int(xs_arr[b[-1]])
    return int(np.percentile(xs_arr, 12)), int(np.percentile(xs_arr, 88))


def _seg(ys):
    if len(ys) < 2: return 0.0
    gaps = np.where(np.diff(ys) > 8)[0]
    if not len(gaps): return float(ys[-1]-ys[0])
    segs, p = [], 0
    for g in gaps: segs.append(ys[g]-ys[p]); p = g+1
    segs.append(ys[-1]-ys[p])
    return float(max(segs))


def medir(image, mask, contour, ac_real_cm=None):
    """
    Extrae features morfológicas de la silueta.
    
    Si ac_real_cm está disponible, calibra la escala px/cm con la AC
    real de esa vaca (mucho más preciso que asumir 123 cm).
    
    Las medidas absolutas (lc_img, pt_img) son estimaciones desde imagen;
    se guardan como features pero las medidas reales del CSV tienen prioridad
    en el entrenamiento.
    """
    h_img, w_img = image.shape[:2]
    x_bb, y_bb, bw, bh = cv2.boundingRect(contour)

    # ── Altura del tronco en píxeles ──────────────────────────────
    max_h_px = 0.0
    for xi in range(x_bb+int(bw*0.25), min(x_bb+int(bw*0.60), w_img)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            max_h_px = max(max_h_px, float(ys[-1]-ys[0]))
    if max_h_px < bh*0.35:
        max_h_px = float(bh)

    # ── Escala: calibrada con AC real o estándar Jersey ───────────
    ac_ref  = ac_real_cm if ac_real_cm and ac_real_cm > 80 else 123.0
    px      = max_h_px / ac_ref    # px por cm

    # ── Lomo ──────────────────────────────────────────────────────
    x_enc, x_isq = detectar_lomo(mask, x_bb, y_bb, bw, bh, w_img)
    lc_px  = max(x_isq-x_enc, 1)
    lc_img = lc_px / px            # LC estimado desde imagen (cm)

    y_fs = y_bb+int(bh*0.10)
    y_fi = y_bb+int(bh*0.70)

    # ── Altura torácica en la columna PT ──────────────────────────
    x_pt  = np.clip(x_enc+int(lc_px*0.22), 0, w_img-1)
    ys_pt = np.where(mask[:, x_pt] > 0)[0]
    ys_t2 = ys_pt[(ys_pt >= y_fs) & (ys_pt <= y_fi)]
    h_tor = float(ys_t2[-1]-ys_t2[0]) if len(ys_t2) >= 2 else _seg(ys_pt)
    h_tor_cm = h_tor / px          # altura torácica real en cm

    # PT estimado desde imagen (solo como referencia, no como feature principal)
    prof   = h_tor * 0.75
    a, b   = h_tor/2, prof/2
    pt_img = np.pi*(3*(a+b)-np.sqrt((3*a+b)*(a+3*b))) / px

    # ── Cadera ────────────────────────────────────────────────────
    x_cad  = np.clip(x_enc+int(lc_px*0.80), 0, w_img-1)
    ys_c   = np.where(mask[:, x_cad] > 0)[0]
    ys_ct  = ys_c[(ys_c >= y_fs) & (ys_c <= y_fi)]
    cad_cm = (float(ys_ct[-1]-ys_ct[0]) if len(ys_ct) >= 2 else _seg(ys_c)) / px

    area  = float(cv2.contourArea(contour))
    perim = float(cv2.arcLength(contour, True))

    # ── Features relativas (invariantes a escala/distancia) ───────
    # Estas son más robustas que las absolutas ante variación de distancia
    lc_rel   = lc_px / max_h_px                    # ratio largo/alto
    perim_rel= perim / max_h_px                     # perímetro normalizado
    area_rel = area / (w_img * h_img)               # área normalizada imagen
    htor_rel = h_tor / max_h_px                     # altura tórax / altura vaca
    cad_rel  = (ys_ct[-1]-ys_ct[0]) / max_h_px if len(ys_ct)>=2 else 0.0

    return {
        # ── Medidas absolutas desde imagen (cm) ──
        "lc_img":      round(lc_img, 2),
        "pt_img":      round(pt_img, 2),
        "ac_img":      round(max_h_px/px, 2),
        "cadera_img":  round(cad_cm, 2),
        "h_tor_cm":    round(h_tor_cm, 2),
        # ── Features relativas (más robustas) ──
        "ratio_lh":    round(lc_rel, 4),
        "perim_norm":  round(perim_rel, 4),
        "area_norm":   round(area_rel, 6),
        "htor_norm":   round(htor_rel, 4),
        "cad_norm":    round(cad_rel, 4),
        # ── Escala y calidad ──
        "px_per_cm":   round(px, 4),
        "ac_ref_cm":   round(ac_ref, 1),
        "confidence":  round(min(area/float(bw*bh),1.0) if bw*bh>0 else 0, 3),
        "sam_score":   0.0,
    }


# ══════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════

filas    = []
errores  = []
total    = len(registros_validos)
t_inicio = time.time()

print(f"{'─'*62}")
print(f"  Procesando {total} imágenes...")
print(f"{'─'*62}")

for i, (vaca_id, img_path) in enumerate(registros_validos, 1):
    t0 = time.time()
    try:
        med      = medidas_dict[vaca_id]
        ac_real  = med.get("ac_real", None)

        # cv2.imread falla con rutas que tienen tildes/caracteres especiales
        # Usamos np.fromfile + imdecode como solución
        import numpy as np_io
        buf = np_io.fromfile(str(img_path), dtype=np_io.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("cv2.imdecode devolvió None (archivo corrupto o formato no soportado)")
        h0, w0 = img.shape[:2]
        if max(h0, w0) > args.max_dim:
            f = args.max_dim/max(h0,w0)
            img = cv2.resize(img, (int(w0*f), int(h0*f)))

        mask, contour, sam_score = segmentar(img)
        if contour is None:
            raise ValueError("SAM sin contorno válido")

        m = medir(img, mask, contour, ac_real_cm=ac_real)
        m["sam_score"] = round(sam_score, 4)

        # Solo descartar segmentaciones claramente fallidas
        if m["confidence"] < 0.15:
            raise ValueError(f"Confianza SAM muy baja: {m['confidence']:.2f}")
        if m["sam_score"] < 0.80:
            raise ValueError(f"Score SAM muy bajo: {m['sam_score']:.3f}")

        fila = {
            "vaca_id":   vaca_id,
            "imagen":    img_path.name,
            # Medidas reales del CSV (ground truth)
            "lc_real":   med.get("lc_real",  None),
            "pt_real":   med.get("pt_real",  None),
            "ac_real":   med.get("ac_real",  None),
            "peso_real": med.get("peso_real", None),
            "bcs":       med.get("bcs",       3.25),
            **m
        }
        filas.append(fila)

        elapsed = time.time()-t0
        cal_tag = f"AC={ac_real:.0f}cm" if ac_real else "AC=123cm(std)"
        print(f"  [{i:>4}/{total}] {vaca_id}/{img_path.name:<22} "
              f"LC_img:{m['lc_img']:>6.1f}  PT_img:{m['pt_img']:>6.1f}  "
              f"r_lh:{m['ratio_lh']:.3f}  [{cal_tag}]  {elapsed:.1f}s")

    except Exception as e:
        errores.append((vaca_id, img_path.name, str(e)))
        print(f"  [{i:>4}/{total}] ⚠ {vaca_id}/{img_path.name} → {e}")

# ══════════════════════════════════════════════════════════
# GUARDAR CSV
# ══════════════════════════════════════════════════════════

df = pd.DataFrame(filas)
df.to_csv(str(SALIDA), index=False)

t_total = time.time()-t_inicio
print(f"\n{SEP}")
print(f"  EXTRACCIÓN COMPLETA")
print(f"{SEP}")
print(f"  Procesadas   : {len(filas)} imágenes")
print(f"  Errores      : {len(errores)}")
print(f"  Vacas        : {df['vaca_id'].nunique()}")
print(f"  Tiempo total : {t_total/60:.1f} min ({t_total/len(registros_validos):.1f}s/img)")
print(f"  CSV guardado : {SALIDA}")

if errores:
    print(f"\n  ⚠ Imágenes con error ({len(errores)}):")
    for v, img, err in errores[:20]:
        print(f"    {v}/{img}: {err}")
    if len(errores) > 20:
        print(f"    ... y {len(errores)-20} más")

print(f"\n  Estadísticas features relativas:")
cols_stat = ["ratio_lh", "htor_norm", "cad_norm", "perim_norm", "area_norm"]
print(df[cols_stat].describe().round(3).to_string())
print(f"\n  Estadísticas medidas imagen (cm):")
print(df[["lc_img","pt_img","ac_img"]].describe().round(1).to_string())
print(f"{SEP}\n")
print("  Siguiente paso:")
print("  python entrenar_modelo.py")
print(f"{SEP}\n")
