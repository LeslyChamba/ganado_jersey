# extraer_features.py  v3
"""
BovineAI — Extracción de features con el nuevo medir() corregido.
Procesa todas las fotos del dataset y genera features_imagenes.csv.

Uso:
  python extraer_features.py
  python extraer_features.py --fotos "ruta/dataset" --pesos pesos_vacas_PLANTILLA.csv
"""
import sys, argparse, warnings, time
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
import cv2

PROYECTO_DIR = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
FOTOS_DIR    = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\Dataset-Vacas\V1")
PESOS_CSV    = PROYECTO_DIR / "pesos_vacas_PLANTILLA.csv"
SAM_MODEL    = PROYECTO_DIR / "models_pt" / "sam_vit_b.pth"
SALIDA_CSV   = PROYECTO_DIR / "features_imagenesv2.csv"
sys.path.insert(0, str(PROYECTO_DIR))

parser = argparse.ArgumentParser()
parser.add_argument("--fotos",    default=str(FOTOS_DIR))
parser.add_argument("--pesos",    default=str(PESOS_CSV))
parser.add_argument("--salida",   default=str(SALIDA_CSV))
parser.add_argument("--reanudar", action="store_true",
                    help="Saltar imágenes ya procesadas")
args = parser.parse_args()

SEP = "═" * 60
print(f"\n{SEP}")
print("  BovineAI — Extracción de features v3")
print(f"{SEP}\n")

# ── Cargar pesos reales ───────────────────────────────────
# Detectar separador y decimales automáticamente
with open(args.pesos, "rb") as f:
    raw = f.read(500).decode("utf-8", errors="replace")
sep = ";" if raw.count(";") > raw.count(",") else ","

df_pesos = pd.read_csv(args.pesos, sep=sep, decimal=",", encoding="utf-8-sig")
df_pesos.columns = [c.strip().lower() for c in df_pesos.columns]

# Renombrar columnas si difieren
col_map = {}
for c in df_pesos.columns:
    cl = c.lower()
    if "vaca" in cl or cl == "id":  col_map[c] = "vaca_id"
    if "lc" in cl:                  col_map[c] = "lc_real"
    if "pt" in cl:                  col_map[c] = "pt_real"
    if "peso" in cl:                col_map[c] = "peso_real"
    if "bcs" in cl:                 col_map[c] = "bcs"
df_pesos = df_pesos.rename(columns=col_map)

# Eliminar filas sin vaca_id válido (ej: fila extra al final)
df_pesos = df_pesos.dropna(subset=["vaca_id"])
df_pesos = df_pesos[df_pesos["vaca_id"].astype(str).str.match(r"V\d+")]
df_pesos["vaca_id"] = df_pesos["vaca_id"].astype(str).str.strip()

# Convertir columnas numéricas (por si quedaron como string con coma)
for col in ["lc_real","pt_real","peso_real","bcs"]:
    if col in df_pesos.columns:
        df_pesos[col] = pd.to_numeric(
            df_pesos[col].astype(str).str.replace(",","."), errors="coerce")

print(f"Pesos cargados: {len(df_pesos)} vacas")
print(f"Columnas: {list(df_pesos.columns)}")
print(f"Rango pesos: {df_pesos['peso_real'].min():.0f} – {df_pesos['peso_real'].max():.0f} kg\n")

# ── Cargar fotos ──────────────────────────────────────────
EXTS = {".jpg",".jpeg",".png",".JPG",".JPEG",".PNG"}
fotos = sorted([f for f in Path(args.fotos).iterdir() if f.suffix in EXTS])
print(f"Fotos encontradas: {len(fotos)} en {args.fotos}\n")

# Reanudar si existe CSV parcial
procesadas = set()
if args.reanudar and Path(args.salida).exists():
    df_exist = pd.read_csv(args.salida)
    procesadas = set(df_exist["imagen"].tolist())
    print(f"Reanudando — ya procesadas: {len(procesadas)} fotos\n")
    rows = df_exist.to_dict("records")
else:
    rows = []

# ── SAM: carga única ──────────────────────────────────────
print("Cargando SAM (vit_b)...")
import torch
from segment_anything import sam_model_registry, SamPredictor
sam = sam_model_registry["vit_b"](checkpoint=str(SAM_MODEL))
device = "cuda" if torch.cuda.is_available() else "cpu"
sam.to(device=device)
predictor = SamPredictor(sam)
print(f"SAM listo [{device}]\n")


# ── Importar medir() desde probar_imagen ─────────────────
# Copia inline de las funciones críticas para independencia

def _seg(ys):
    if len(ys) < 2: return 0.0
    gaps = np.where(np.diff(ys) > 8)[0]
    if not len(gaps): return float(ys[-1]-ys[0])
    segs, p = [], 0
    for g in gaps:
        segs.append(ys[g]-ys[p]); p = g+1
    segs.append(ys[-1]-ys[p])
    return float(max(segs))


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


def _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado):
    y_ini   = y_bb + int(bh * 0.18)
    y_fin   = y_bb + int(bh * 0.60)
    min_px  = int(bh * 0.10)
    margen_enc = int(bw * 0.28)
    margen_isq = int(bw * 0.22)
    if lado == "derecha":
        x_ini = x_bb + int(bw * 0.50)
        x_fin = x_bb + bw - margen_enc
        for xi in range(min(x_fin, mask.shape[1])-1, x_ini, -1):
            ys = np.where(mask[y_ini:y_fin, xi] > 0)[0]
            if len(ys) >= min_px: return xi
        return x_bb + bw - margen_enc
    else:
        x_ini = x_bb + margen_isq
        x_fin = x_bb + int(bw * 0.50)
        for xi in range(x_ini, min(x_fin, mask.shape[1])):
            ys = np.where(mask[y_ini:y_fin, xi] > 0)[0]
            if len(ys) >= min_px: return xi
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
        np.median(tops_arr[max(0,i-win):i+win+1])
        for i in range(len(tops_arr))
    ])
    orientacion = detectar_orientacion(mask, x_bb, y_bb, bw, bh)
    mg = int(len(xs_arr) * 0.10)
    zona_tops = tops_smooth[mg:len(xs_arr)-mg]
    umbral    = np.percentile(zona_tops, 30)
    tol       = bh * 0.05
    en_lomo   = tops_smooth <= (umbral + tol)
    en_lomo[:mg] = False; en_lomo[len(xs_arr)-mg:] = False
    idx_lomo = np.where(en_lomo)[0]
    if len(idx_lomo) >= 5:
        gaps = np.where(np.diff(idx_lomo) > max(len(xs_arr)*0.05,3))[0]
        bloques, prev = [], 0
        for g in gaps:
            bloques.append(idx_lomo[prev:g+1]); prev = g+1
        bloques.append(idx_lomo[prev:])
        if orientacion == "derecha":
            x_enc = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="derecha")
            x_isq = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="izquierda")
        else:
            x_enc = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="izquierda")
            x_isq = _detectar_columna_pata(mask, x_bb, y_bb, bw, bh, lado="derecha")
    else:
        if orientacion == "derecha":
            x_enc = int(np.percentile(xs_arr, 22)); x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78)); x_isq = int(np.percentile(xs_arr, 22))
    if abs(x_isq - x_enc) < bw * 0.20:
        if orientacion == "derecha":
            x_enc = int(np.percentile(xs_arr, 22)); x_isq = int(np.percentile(xs_arr, 78))
        else:
            x_enc = int(np.percentile(xs_arr, 78)); x_isq = int(np.percentile(xs_arr, 22))
    return x_enc, x_isq, tops_smooth.tolist(), xs_validos, orientacion


def segmentar(image_bgr):
    h, w = image_bgr.shape[:2]
    predictor.set_image(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    cx, cy = w//2, h//2
    fg_pts = np.array([
        [cx,cy],[cx-w//6,cy],[cx+w//6,cy],[cx,cy-h//6],[cx,cy+h//8],
        [cx-w//4,cy-h//8],[cx+w//4,cy-h//8],[cx-w//6,cy+h//10],[cx+w//6,cy+h//10]
    ])
    bg_pts = np.array([[10,10],[w-10,10],[10,h-10],[w-10,h-10],
                       [cx,10],[10,cy],[w-10,cy],[cx,h-10]])
    all_pts = np.vstack([fg_pts, bg_pts])
    all_lbl = np.array([1]*len(fg_pts)+[0]*len(bg_pts))
    masks, scores, _ = predictor.predict(
        point_coords=all_pts, point_labels=all_lbl, multimask_output=True)
    mejor_score, mejor_mask = -1, None
    for mask, score in zip(masks, scores):
        fill = mask.sum()/(h*w)
        if 0.08 <= fill <= 0.80 and score > mejor_score:
            mejor_score = score; mejor_mask = mask
    if mejor_mask is None:
        mejor_mask = masks[np.argmax(scores)]
    mask_bin = mejor_mask.astype(np.uint8)*255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15))
    mask_bin = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, k)
    cnts,_ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts: return mask_bin, None, mejor_score
    main = max(cnts, key=cv2.contourArea)
    mc = np.zeros_like(mask_bin)
    cv2.drawContours(mc,[main],-1,255,-1)
    return mc, main, mejor_score


def medir(image, mask, contour):
    h_img, w_img = image.shape[:2]
    x_bb, y_bb, bw, bh = cv2.boundingRect(contour)

    # Escala: percentil 85 en zona central
    alturas = []
    x_ac = 0; max_h_px = 0.0
    for xi in range(x_bb+int(bw*0.25), min(x_bb+int(bw*0.60), w_img)):
        ys = np.where(mask[:,xi]>0)[0]
        if len(ys)>=2:
            h = float(ys[-1]-ys[0])
            alturas.append((h,xi))
            if h>max_h_px: max_h_px=h; x_ac=xi
    if alturas:
        alturas.sort(key=lambda x:x[0])
        idx85 = int(len(alturas)*0.85)
        max_h_px = alturas[idx85][0]; x_ac = alturas[idx85][1]
    if max_h_px < bh*0.35: max_h_px=float(bh); x_ac=x_bb+bw//2
    px = max_h_px / 123.0

    x_enc, x_isq, tops_smooth, xs_validos, orientacion = detectar_lomo(
        mask, x_bb, y_bb, bw, bh, w_img)
    lc_px = max(abs(x_isq-x_enc),1)
    x_izq = min(x_enc,x_isq); x_der = max(x_enc,x_isq)
    lc_cm = (lc_px/px) + 0.50

    # PT con detección automática de gap
    if orientacion=="derecha":
        x_pt = np.clip(x_der - int(lc_px*0.28), 0, w_img-1)
    else:
        x_pt = np.clip(x_izq + int(lc_px*0.28), 0, w_img-1)
    y_tor_top = y_bb + int(bh*0.05)
    ys_pt_all = np.where(mask[:,x_pt]>0)[0]
    ys_cuerpo = ys_pt_all[ys_pt_all >= y_tor_top]
    y_tor_bot = y_bb + int(bh*0.55)
    if len(ys_cuerpo)>=4:
        diffs = np.diff(ys_cuerpo)
        gaps_idx = np.where(diffs > max(bh*0.04,8))[0]
        if len(gaps_idx)>0:
            y_tor_bot = int(ys_cuerpo[gaps_idx[0]])
        else:
            y_tor_bot = y_bb + int(bh*0.52)
    ys_tor = ys_pt_all[(ys_pt_all>=y_tor_top)&(ys_pt_all<=y_tor_bot)]
    h_tor  = float(ys_tor[-1]-ys_tor[0]) if len(ys_tor)>=2 else _seg(ys_pt_all)
    pt_cm  = (h_tor*np.pi)/px

    y_fs = y_tor_top; y_fi = y_tor_bot

    # AG
    ys_ag = np.where(mask[:,x_isq]>0)[0]
    ag_cm = float(ys_ag[-1]-ys_ag[0])/px if len(ys_ag)>=2 else max_h_px/px

    # Cadera
    x_cad = np.clip(x_izq+int(lc_px*0.80),0,w_img-1)
    ys_c  = np.where(mask[:,x_cad]>0)[0]
    ys_ct = ys_c[(ys_c>=y_fs)&(ys_c<=y_fi)]
    cad_cm = (float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else _seg(ys_c))/px

    area  = float(cv2.contourArea(contour))
    perim = float(cv2.arcLength(contour,True))
    cad_h_px = float(ys_ct[-1]-ys_ct[0]) if len(ys_ct)>=2 else 0.0

    return {
        "lc_img":      round(lc_cm,2),
        "pt_img":      round(pt_cm,2),
        "ac_img":      round(max_h_px/px,1),
        "cadera_img":  round(cad_cm,2),
        "h_tor_cm":    round(h_tor/px,2),
        "ratio_lh":    round(lc_px/max_h_px if max_h_px>0 else 1,4),
        "perim_norm":  round(perim/max_h_px if max_h_px>0 else 1,4),
        "area_norm":   round(area/(w_img*h_img),5),
        "htor_norm":   round(h_tor/max_h_px if max_h_px>0 else 0,4),
        "cad_norm":    round(cad_h_px/max_h_px if max_h_px>0 else 0,4),
        "px_per_cm":   round(px,4),
        "confidence":  round(min(area/float(bw*bh),1.0) if bw*bh>0 else 0,3),
        "orientacion": orientacion,
    }


# ── Procesar ──────────────────────────────────────────────
total = len(fotos); ok = 0; err = 0
t_total = time.time()

for i, foto_path in enumerate(fotos, 1):
    nombre = foto_path.name
    if nombre in procesadas:
        continue

    # Extraer vaca_id del nombre (ej: "V33 (29).jpg" → "V33")
    import re
    m = re.match(r"(V\d+)", nombre)
    if not m:
        print(f"  ⚠ Saltando {nombre} (no coincide patrón V##)")
        continue
    vaca_id = m.group(1)

    # Buscar datos reales
    fila = df_pesos[df_pesos["vaca_id"]==vaca_id]
    if len(fila)==0:
        continue  # vaca sin datos de peso → saltar silenciosamente

    peso_real = float(fila["peso_real"].iloc[0]) if "peso_real" in fila.columns else None
    lc_real   = float(fila["lc_real"].iloc[0])   if "lc_real"   in fila.columns else None
    pt_real   = float(fila["pt_real"].iloc[0])   if "pt_real"   in fila.columns else None
    ac_real   = float(fila["ac_real"].iloc[0])   if "ac_real"   in fila.columns else None
    bcs_val   = float(fila["bcs"].iloc[0])        if "bcs"       in fila.columns else 3.25

    try:
        # Leer imagen
        img_bytes = np.fromfile(str(foto_path), dtype=np.uint8)
        img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
        if img is None: raise ValueError("cv2.imdecode falló")
        h0,w0 = img.shape[:2]
        if max(h0,w0)>1280:
            f=1280/max(h0,w0); img=cv2.resize(img,(int(w0*f),int(h0*f)))

        mask, contour, sam_score = segmentar(img)
        if contour is None: raise ValueError("Sin contorno SAM")

        feat = medir(img, mask, contour)

        row = {
            "vaca_id":    vaca_id,
            "imagen":     nombre,
            "lc_real":    lc_real,
            "pt_real":    pt_real,
            "ac_real":    ac_real,
            "peso_real":  peso_real,
            "bcs":        bcs_val,
            "sam_score":  round(sam_score, 4),
            **feat,
        }
        rows.append(row)
        ok += 1

        # Guardar cada 10 fotos
        if ok % 10 == 0:
            pd.DataFrame(rows).to_csv(args.salida, index=False)

        elapsed = time.time()-t_total
        rate    = ok/elapsed if elapsed>0 else 0
        eta     = (total-i)/rate if rate>0 else 0
        print(f"  [{i:4d}/{total}] {vaca_id:<6} {nombre:<25} "
              f"LC:{feat['lc_img']:5.1f} PT:{feat['pt_img']:5.1f} "
              f"conf:{feat['confidence']:.2f} "
              f"ETA:{eta/60:.0f}min", flush=True)

    except Exception as e:
        print(f"  ❌ {nombre}: {e}")
        err += 1

# Guardar final
df_out = pd.DataFrame(rows)
df_out.to_csv(args.salida, index=False)

elapsed = time.time()-t_total
print(f"\n{SEP}")
print(f"  Procesadas : {ok} fotos OK | {err} errores")
print(f"  Vacas      : {df_out['vaca_id'].nunique()}")
print(f"  Tiempo     : {elapsed/60:.1f} min")
print(f"  CSV        : {args.salida}")
print(f"  LC promedio: {df_out['lc_img'].mean():.1f} cm")
print(f"  PT promedio: {df_out['pt_img'].mean():.1f} cm")
print(f"{SEP}\n")
print("Siguiente paso:")
print("  python entrenarM_peso.py")