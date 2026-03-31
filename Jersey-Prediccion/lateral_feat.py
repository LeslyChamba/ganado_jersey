"""
extraer_features_lateral.py — Extrae medidas morfológicas de fotos LATERALES
=============================================================================
Features extraídas por vaca (promedio de todas sus fotos laterales válidas):
  - largo_cm       : longitud corporal horizontal
  - alzada_cm      : altura (bbox height calibrada)
  - prof_tor_cm    : profundidad torácica (zona 25-50% del largo)
  - ratio_L_A      : largo/alzada  (índice de formato)
  - ratio_PT_A     : prof_tor/alzada

Uso:
  python extraer_features_lateral.py

Salida:
  lateral_features.csv
"""

import cv2, base64, time
import numpy as np
import pandas as pd
from pathlib import Path

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
CARPETA_IMGS    = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\BCS\imagenes_recortadas")
PROYECTO_DIR    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
CSV_PESOS       = PROYECTO_DIR / "pesos_vacas_PLANTILLA.csv"
CSV_PT_ROB      = PROYECTO_DIR / "pt_rob_dataset.csv"          # ya generado
OUTPUT_CSV      = PROYECTO_DIR / "lateral_features.csv"
DEBUG_DIR       = PROYECTO_DIR / "debug_lateral"

ROBOFLOW_API_KEY = "UjQmJp4eMxIZASwVa7Kk"
ROBOFLOW_MODEL   = "cattle-body-pfmdu/1"

# Alzada referencia Jersey cm — para calibrar escala en fotos laterales
AC_REF_LATERAL  = 123.0

# Rango fisiológico lateral Jersey
LARGO_MIN, LARGO_MAX   = 120, 240   # cm
ALZADA_MIN, ALZADA_MAX = 100, 155   # cm


# ── HELPERS ───────────────────────────────────────────────────────────────────

def buscar_todas_imagenes(carpeta: Path, vaca_id: str) -> list:
    todas = []
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        todas += sorted(carpeta.glob(f"{vaca_id}-*{ext}"))
        exacta = carpeta / f"{vaca_id}{ext}"
        if exacta.exists():
            todas.append(exacta)
        todas += sorted(carpeta.glob(f"{vaca_id} (*){ext}"))
    vistas, resultado = set(), []
    for p in todas:
        if p not in vistas:
            vistas.add(p)
            resultado.append(p)
    return resultado


def es_foto_lateral(bw: int, bh: int) -> bool:
    """
    Una foto lateral tiene ratio ancho/alto > 1.3 (la vaca es más larga que alta).
    Una foto trasera tiene ratio ~0.6-0.9 (la vaca es más alta que ancha).
    """
    if bh == 0:
        return False
    ratio = bw / bh
    return ratio > 1.25  # lateral si la caja es más ancha que alta


def medir_lateral(img_path: Path, client, debug_path: Path = None) -> dict | None:
    """
    Segmenta la vaca y extrae medidas morfológicas laterales.
    Retorna None si la foto no es lateral o la segmentación falla.
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    h_i, w_i = img.shape[:2]

    _, buf = cv2.imencode(".jpg", img)
    b64 = base64.b64encode(buf).decode()

    res = None
    for model in [ROBOFLOW_MODEL, "live_cattle/1"]:
        try:
            r = client.infer(b64, model_id=model)
            if r.get("predictions"):
                res = r
                break
        except:
            continue

    if not res or not res.get("predictions"):
        return None

    pred = max(res["predictions"], key=lambda x: x["confidence"])
    pts  = np.array([[p["x"], p["y"]] for p in pred["points"]], dtype=np.int32)
    mask = np.zeros((h_i, w_i), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    xb, yb, bw, bh = cv2.boundingRect(pts)

    # Solo aceptar fotos laterales
    if not es_foto_lateral(bw, bh):
        return None

    # Escala: la alzada (bbox height) ≈ AC_REF_LATERAL cm
    px_per_cm = bh / AC_REF_LATERAL if bh > 0 else 1.0

    # 1. Largo corporal: ancho máximo de la máscara
    largo_px = bw
    largo_cm = largo_px / px_per_cm

    # 2. Alzada real (por coherencia, usar bh directamente)
    alzada_cm = bh / px_per_cm  # debería ser ~AC_REF_LATERAL

    # 3. Profundidad torácica: medir altura de la máscara en zona 25-50% del largo
    x_start = xb + int(bw * 0.25)
    x_end   = xb + int(bw * 0.50)
    prof_max_px = 0
    for xi in range(x_start, min(x_end, w_i)):
        ys = np.where(mask[:, xi] > 0)[0]
        if len(ys) >= 2:
            h_col = int(ys[-1] - ys[0])
            if h_col > prof_max_px:
                prof_max_px = h_col
    prof_tor_cm = prof_max_px / px_per_cm

    # Filtros fisiológicos
    if not (LARGO_MIN <= largo_cm <= LARGO_MAX):
        return None
    if not (ALZADA_MIN <= alzada_cm <= ALZADA_MAX):
        return None
    if prof_tor_cm < 30 or prof_tor_cm > 90:
        return None

    # Debug visual
    if debug_path:
        ov = img.copy()
        overlay = img.copy()
        cv2.fillPoly(overlay, [pts], (0, 140, 255))
        cv2.addWeighted(ov, 0.65, overlay, 0.35, 0, ov)
        cv2.polylines(ov, [pts], True, (0, 200, 255), 2)
        cv2.rectangle(ov, (xb, yb), (xb + bw, yb + bh), (255, 255, 0), 1)
        # Línea largo
        y_mid = yb + bh // 2
        cv2.line(ov, (xb, y_mid), (xb + bw, y_mid), (0, 255, 100), 2)
        cv2.putText(ov, f"L={largo_cm:.0f}cm", (xb + 5, y_mid - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 100), 2)
        # Línea profundidad torácica
        x_tor = xb + int(bw * 0.37)
        cv2.line(ov, (x_tor, yb), (x_tor, yb + prof_max_px), (255, 80, 0), 3)
        cv2.putText(ov, f"PT={prof_tor_cm:.0f}cm", (x_tor + 5, yb + prof_max_px // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 80, 0), 2)
        cv2.putText(ov, f"conf={pred['confidence']:.2f}  {img_path.name}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.imwrite(str(debug_path), ov)

    return {
        "largo_px"    : largo_px,
        "largo_cm"    : round(largo_cm, 1),
        "alzada_cm"   : round(alzada_cm, 1),
        "prof_tor_px" : prof_max_px,
        "prof_tor_cm" : round(prof_tor_cm, 1),
        "alto_bbox_px": bh,
        "px_per_cm"   : round(px_per_cm, 3),
        "confianza"   : round(pred["confidence"], 3),
        "escala_ok"   : bh >= 250,
        "img_usada"   : img_path.name,
    }


def procesar_vaca_lateral(carpeta: Path, vaca_id: str, client, debug_dir: Path = None) -> dict:
    """
    Intenta TODAS las fotos de la vaca, promedia las medidas de las laterales válidas.
    """
    fotos = buscar_todas_imagenes(carpeta, vaca_id)
    if not fotos:
        raise ValueError("sin imágenes")

    candidatos = []
    mejor_conf = -1
    mejor_result_path = None

    for img_path in fotos[:10]:  # máximo 10 fotos
        dbg = None
        if debug_dir:
            dbg = debug_dir / f"lat_{vaca_id}_{img_path.stem}.jpg"

        r = medir_lateral(img_path, client, debug_path=dbg)
        if r is not None:
            candidatos.append(r)
            if r["confianza"] > mejor_conf:
                mejor_conf = r["confianza"]
                mejor_result_path = img_path

        time.sleep(0.15)

    if not candidatos:
        raise ValueError("ninguna foto lateral válida")

    # Promediar todas las medidas laterales válidas
    resultado = {
        "largo_cm"    : round(np.mean([c["largo_cm"]    for c in candidatos]), 1),
        "alzada_cm"   : round(np.mean([c["alzada_cm"]   for c in candidatos]), 1),
        "prof_tor_cm" : round(np.mean([c["prof_tor_cm"] for c in candidatos]), 1),
        "alto_bbox_px": round(np.mean([c["alto_bbox_px"]for c in candidatos])),
        "px_per_cm"   : round(np.mean([c["px_per_cm"]   for c in candidatos]), 3),
        "conf_lat"    : round(np.mean([c["confianza"]   for c in candidatos]), 3),
        "escala_ok"   : sum(c["escala_ok"] for c in candidatos) > len(candidatos) / 2,
        "n_laterales" : len(candidatos),
        "n_total_fotos": len(fotos),
    }
    resultado["ratio_L_A"]  = round(resultado["largo_cm"]    / resultado["alzada_cm"], 3)
    resultado["ratio_PT_A"] = round(resultado["prof_tor_cm"] / resultado["alzada_cm"], 3)

    return resultado


# ── MAIN ──────────────────────────────────────────────────────────────────────

from inference_sdk import InferenceHTTPClient

client = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key=ROBOFLOW_API_KEY)

df_pesos = pd.read_csv(str(CSV_PESOS), sep=";", decimal=",")
df_pesos = df_pesos.dropna(subset=["vaca_id", "peso_real"])
vacas    = df_pesos["vaca_id"].astype(str).tolist()

SEP = "═" * 65
print(f"\n{SEP}")
print(f"  extraer_features_lateral.py — {len(vacas)} vacas")
print(f"  Extrae: largo_cm, alzada_cm, prof_tor_cm, ratios")
print(f"{SEP}\n")

DEBUG_DIR.mkdir(parents=True, exist_ok=True)
resultados, errores = [], []

for i, vaca_id in enumerate(vacas, 1):
    n_fotos = len(buscar_todas_imagenes(CARPETA_IMGS, vaca_id))
    print(f"[{i:2d}/{len(vacas)}] {vaca_id:5s} ({n_fotos} fotos)  ", end="", flush=True)

    if n_fotos == 0:
        print("⚠ sin imágenes")
        errores.append(vaca_id)
        continue

    try:
        r = procesar_vaca_lateral(CARPETA_IMGS, vaca_id, client, debug_dir=DEBUG_DIR)
        peso_r = float(df_pesos[df_pesos["vaca_id"] == vaca_id]["peso_real"].values[0])
        resultados.append({"vaca_id": vaca_id, "peso_real": peso_r, **r})
        estado = "✓" if r["escala_ok"] else "⚠ pequeña"
        print(f"L={r['largo_cm']:.0f}cm  A={r['alzada_cm']:.0f}cm  "
              f"PT={r['prof_tor_cm']:.0f}cm  "
              f"n_lat={r['n_laterales']}  conf={r['conf_lat']:.2f}  {estado}")
    except Exception as e:
        print(f"❌ {e}")
        errores.append(vaca_id)

# Guardar
df_lat = pd.DataFrame(resultados)
df_lat.to_csv(str(OUTPUT_CSV), index=False)

print(f"\n{SEP}  RESUMEN")
print(f"  Procesadas : {len(resultados)} / {len(vacas)}")
print(f"  Errores    : {errores}")
if len(resultados) > 0:
    for col in ["largo_cm", "alzada_cm", "prof_tor_cm"]:
        print(f"  {col:14s}: {df_lat[col].mean():.1f} cm  "
              f"(min {df_lat[col].min():.1f} — max {df_lat[col].max():.1f})")
    for col in ["largo_cm", "alzada_cm", "prof_tor_cm"]:
        corr = df_lat[col].corr(df_lat["peso_real"])
        print(f"  Corr {col:10s}/peso: {corr:.3f}")
print(f"\n  Guardado: {OUTPUT_CSV}")
print(f"  Debug   : {DEBUG_DIR}/")
print(f"{SEP}\n")