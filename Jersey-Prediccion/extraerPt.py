"""
extraer_pt_rob.py — Recolecta pt_rob de fotos traseras con Roboflow
====================================================================
Lee las fotos traseras completas de la carpeta BCS
Calcula pt_rob = (ancho_tor_px / px_per_cm) × π para cada vaca
Guarda: pt_rob_dataset.csv

Uso:
  python extraer_pt_rob.py
"""
import cv2, base64, time
import numpy as np
import pandas as pd
from pathlib import Path

# ── CONFIGURACIÓN ────────────────────────────────────────────────
CARPETA_TRASERA = Path(r"C:\Users\HP\OneDrive - ESCUELA SUPERIOR POLITECNICA DE CHIMBORAZO\Escritorio\BCS\imagenes_recortadas")
PROYECTO_DIR    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
CSV_PESOS       = PROYECTO_DIR / "pesos_vacas_PLANTILLA.csv"
OUTPUT_CSV      = PROYECTO_DIR / "pt_rob_dataset.csv"
DEBUG_DIR       = PROYECTO_DIR / "debug_pt_rob"

ROBOFLOW_API_KEY = "UjQmJp4eMxIZASwVa7Kk"
ROBOFLOW_MODEL   = "cattle-body-pfmdu/1"
AC_REF           = 123.0  # alzada referencia Jersey cm


# ── BUSCAR IMAGEN ─────────────────────────────────────────────────

def buscar_todas_imagenes(carpeta: Path, vaca_id: str) -> list:
    """Retorna TODAS las fotos disponibles de la vaca, ordenadas por preferencia."""
    todas = []
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        # Con guión primero (más probable que sean traseras)
        todas += sorted(carpeta.glob(f"{vaca_id}-*{ext}"))
        # Exactas
        exacta = carpeta / f"{vaca_id}{ext}"
        if exacta.exists():
            todas.append(exacta)
        # Con paréntesis
        todas += sorted(carpeta.glob(f"{vaca_id} (*){ext}"))
    # Eliminar duplicados manteniendo orden
    vistas = set()
    resultado = []
    for p in todas:
        if p not in vistas:
            vistas.add(p)
            resultado.append(p)
    return resultado


def buscar_imagen(carpeta: Path, vaca_id: str) -> Path:
    """Retorna la primera foto — se usa solo si medir_pt_rob_mejor falla."""
    fotos = buscar_todas_imagenes(carpeta, vaca_id)
    return fotos[0] if fotos else None


def medir_pt_rob_mejor(carpeta: Path, vaca_id: str, debug_dir: Path = None):
    """
    Intenta TODAS las fotos de la vaca y devuelve la que dé el pt_rob
    más cercano al promedio fisiológico Jersey (178 cm).
    Descarta automáticamente fotos laterales (pt_rob fuera de 140-215 cm).
    """
    from inference_sdk import InferenceHTTPClient
    import base64

    fotos = buscar_todas_imagenes(carpeta, vaca_id)
    if not fotos:
        raise ValueError("imagen no encontrada")

    client = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key=ROBOFLOW_API_KEY)

    candidatos = []
    for img_path in fotos[:8]:  # máximo 8 fotos por vaca para no abusar del API
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            h_i, w_i = img.shape[:2]
            _, buf = cv2.imencode(".jpg", img)
            b64 = base64.b64encode(buf).decode()

            res = None
            for model in [ROBOFLOW_MODEL, "live_cattle/1"]:
                try:
                    r = client.infer(b64, model_id=model)
                    if r.get("predictions"):
                        res = r; break
                except: continue

            if not res or not res.get("predictions"):
                continue

            pred  = max(res["predictions"], key=lambda x: x["confidence"])
            pts   = np.array([[p["x"],p["y"]] for p in pred["points"]], dtype=np.int32)
            mask  = np.zeros((h_i,w_i), dtype=np.uint8)
            cv2.fillPoly(mask, [pts], 255)
            xb, yb, bw, bh = cv2.boundingRect(pts)

            px_per_cm = bh / AC_REF if bh > 0 else 1.0
            y_tt = yb + int(bh*0.20); y_tb = yb + int(bh*0.45)
            ancho_tor = 0; y_best = y_tt
            for yi in range(y_tt, min(y_tb, h_i)):
                xs = np.where(mask[yi,:] > 0)[0]
                if len(xs) >= 2:
                    a = int(xs[-1]-xs[0])
                    if a > ancho_tor:
                        ancho_tor = a; y_best = yi

            if ancho_tor == 0: continue
            ancho_cm = ancho_tor / px_per_cm
            pt_r = ancho_cm * np.pi

            # Solo aceptar valores fisiológicamente posibles
            if 140 <= pt_r <= 215:
                candidatos.append({
                    "pt_rob"       : round(pt_r, 1),
                    "ancho_tor_px" : ancho_tor,
                    "ancho_tor_cm" : round(ancho_cm, 1),
                    "ancho_cad_px" : 0,
                    "alto_bbox_px" : bh,
                    "px_per_cm"    : round(px_per_cm, 3),
                    "confianza_rob": round(pred["confidence"], 3),
                    "img_w"        : w_i,
                    "img_h"        : h_i,
                    "escala_ok"    : bh >= 250,
                    "img_usada"    : img_path.name,
                    "_mask"        : mask,
                    "_img"         : img,
                    "_y_best"      : y_best,
                    "_pts"         : pts,
                    "_xb":xb,"_yb":yb,"_bw":bw,"_bh":bh,
                })

        except Exception as e_foto:
            # Mostrar el error real para diagnóstico
            pass

        time.sleep(0.2)

    if not candidatos:
        raise ValueError("ninguna foto trasera válida (todas laterales)")

    # Usar el PROMEDIO de todos los candidatos válidos
    # NO "más cercano a 178" — ese criterio destruye la variación real entre vacas
    pt_vals = [c["pt_rob"] for c in candidatos]
    pt_promedio = float(np.mean(pt_vals))

    # Elegir el candidato más cercano al promedio real (para el debug visual)
    mejor = min(candidatos, key=lambda x: abs(x["pt_rob"] - pt_promedio))
    mejor["pt_rob"] = round(pt_promedio, 1)  # usar el promedio, no el individual
    mejor["n_candidatos"] = len(candidatos)
    mejor["pt_vals"] = pt_vals

    # Debug visual del mejor candidato
    if debug_dir and "_img" in mejor:
        debug_dir.mkdir(parents=True, exist_ok=True)
        ov = mejor["_img"].copy(); overlay = mejor["_img"].copy()
        pts_d = mejor["_pts"]
        cv2.fillPoly(overlay, [pts_d], (0,200,100))
        cv2.addWeighted(ov, 0.6, overlay, 0.4, 0, ov)
        cv2.polylines(ov, [pts_d], True, (0,255,100), 2)
        xb,yb,bw,bh = mejor["_xb"],mejor["_yb"],mejor["_bw"],mejor["_bh"]
        cv2.rectangle(ov, (xb,yb),(xb+bw,yb+bh),(255,255,0),1)
        ym = mejor["_y_best"]
        xs_t = np.where(mejor["_mask"][ym,:] > 0)[0]
        if len(xs_t) >= 2:
            cv2.line(ov,(xs_t[0],ym),(xs_t[-1],ym),(255,100,0),3)
            cv2.putText(ov, f"Tor:{mejor['ancho_tor_px']}px={mejor['ancho_tor_cm']:.0f}cm PT={mejor['pt_rob']:.0f}cm",
                        (xs_t[0],ym-8), cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,100,0),2)
        ppc = mejor["px_per_cm"]
        color = (60,220,60) if mejor["escala_ok"] else (0,100,255)
        cv2.putText(ov, f"H:{bh}px px/cm={ppc:.2f} {mejor['img_usada']}",
                    (10,25), cv2.FONT_HERSHEY_SIMPLEX,0.5,color,2)
        cv2.putText(ov, f"Intentos OK: {len(candidatos)}/{min(len(fotos),8)}",
                    (10,50), cv2.FONT_HERSHEY_SIMPLEX,0.45,(200,200,200),1)
        cv2.imwrite(str(debug_dir / f"debug_rob_{vaca_id}.jpg"), ov)

    return mejor


# ── MEDIR PT_ROB CON ROBOFLOW ─────────────────────────────────────

def medir_pt_rob(img_path: Path, debug_dir: Path = None) -> dict:
    """
    Segmenta la vaca con Roboflow y calcula pt_rob.
    pt_rob = (ancho_torácico_cm) × π
    Retorna dict con pt_rob y métricas de calidad.
    """
    from inference_sdk import InferenceHTTPClient

    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"No se pudo leer: {img_path}")
    h_i, w_i = img.shape[:2]

    _, buf = cv2.imencode(".jpg", img)
    b64    = base64.b64encode(buf).decode()

    client = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key=ROBOFLOW_API_KEY)

    res = None
    for model in [ROBOFLOW_MODEL, "live_cattle/1"]:
        try:
            r = client.infer(b64, model_id=model)
            if r.get("predictions"):
                res = r
                break
        except:
            continue

    if res is None or not res.get("predictions"):
        raise ValueError("Roboflow no detectó vaca")

    pred  = max(res["predictions"], key=lambda x: x["confidence"])
    pts   = np.array([[p["x"],p["y"]] for p in pred["points"]], dtype=np.int32)
    mask  = np.zeros((h_i,w_i), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    xb, yb, bw, bh = cv2.boundingRect(pts)

    # Escala propia de la foto trasera
    px_per_cm = bh / AC_REF if bh > 0 else 1.0

    # Ancho torácico: zona 20-45% desde arriba del bbox
    y_tt = yb + int(bh * 0.20)
    y_tb = yb + int(bh * 0.45)
    ancho_tor = 0
    y_tor_best = y_tt
    for yi in range(y_tt, min(y_tb, h_i)):
        xs = np.where(mask[yi, :] > 0)[0]
        if len(xs) >= 2:
            a = int(xs[-1] - xs[0])
            if a > ancho_tor:
                ancho_tor = a
                y_tor_best = yi

    # Ancho caderas: zona 45-70%
    y_ct = yb + int(bh * 0.45)
    y_cb = yb + int(bh * 0.70)
    ancho_cad = 0
    for yi in range(y_ct, min(y_cb, h_i)):
        xs = np.where(mask[yi, :] > 0)[0]
        if len(xs) >= 2:
            ancho_cad = max(ancho_cad, int(xs[-1]-xs[0]))

    if ancho_tor == 0:
        raise ValueError("No se pudo medir ancho torácico")

    ancho_tor_cm = ancho_tor / px_per_cm
    pt_rob       = ancho_tor_cm * np.pi

    # Filtro fisiológico Jersey: PT real entre 148–210 cm
    # Si está fuera → la foto es lateral o la segmentación falló
    if pt_rob < 140 or pt_rob > 215:
        raise ValueError(
            f"pt_rob={pt_rob:.0f}cm fuera del rango fisiológico (140-215 cm) "
            f"— foto probablemente lateral, no trasera"
        )
    fill         = mask.sum() / (bw*bh) if bw*bh > 0 else 0

    # Debug visual
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        ov = img.copy(); overlay = img.copy()
        cv2.fillPoly(overlay, [pts], (0,200,100))
        cv2.addWeighted(ov, 0.6, overlay, 0.4, 0, ov)
        cv2.polylines(ov, [pts], True, (0,255,100), 2)
        cv2.rectangle(ov, (xb,yb), (xb+bw,yb+bh), (255,255,0), 1)
        # Línea ancho torácico
        xs_t = np.where(mask[y_tor_best,:] > 0)[0]
        if len(xs_t) >= 2:
            cv2.line(ov,(xs_t[0],y_tor_best),(xs_t[-1],y_tor_best),(255,100,0),3)
            cv2.putText(ov, f"Tor:{ancho_tor}px={ancho_tor_cm:.0f}cm PT={pt_rob:.0f}cm",
                        (xs_t[0],y_tor_best-8), cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,100,0),2)
        # Línea caderas
        ym_c = (y_ct+y_cb)//2
        xs_c = np.where(mask[min(ym_c,h_i-1),:] > 0)[0]
        if len(xs_c) >= 2:
            cv2.line(ov,(xs_c[0],ym_c),(xs_c[-1],ym_c),(100,0,255),3)
        # Alto bbox y escala
        cv2.line(ov,(xb+bw+5,yb),(xb+bw+5,yb+bh),(0,255,255),2)
        color = (60,220,60) if bh >= 250 else (0,100,255)
        cv2.putText(ov, f"H:{bh}px px/cm={px_per_cm:.2f} {'OK' if bh>=250 else 'PEQUEÑA'}",
                    (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        nombre_img = img_path.stem
        cv2.imwrite(str(debug_dir / f"debug_rob_{nombre_img}.jpg"), ov)

    return {
        "pt_rob"       : round(pt_rob, 1),
        "ancho_tor_px" : ancho_tor,
        "ancho_tor_cm" : round(ancho_tor_cm, 1),
        "ancho_cad_px" : ancho_cad,
        "alto_bbox_px" : bh,
        "px_per_cm"    : round(px_per_cm, 3),
        "confianza_rob": round(pred["confidence"], 3),
        "img_w"        : w_i,
        "img_h"        : h_i,
        "escala_ok"    : bh >= 250,
    }


# ── MAIN ─────────────────────────────────────────────────────────

df_pesos = pd.read_csv(str(CSV_PESOS), sep=";", decimal=",")
df_pesos = df_pesos.dropna(subset=["vaca_id","peso_real"])
vacas    = df_pesos["vaca_id"].astype(str).tolist()

SEP = "═" * 60
print(f"\n{SEP}")
print(f"  extraer_pt_rob.py — {len(vacas)} vacas")
print(f"  Carpeta: {CARPETA_TRASERA.name}")
print(f"  Estrategia: prueba TODAS las fotos, elige la mejor trasera")
print(f"{SEP}\n")

DEBUG_DIR.mkdir(parents=True, exist_ok=True)

resultados = []
errores    = []

for i, vaca_id in enumerate(vacas, 1):
    n_fotos = len(buscar_todas_imagenes(CARPETA_TRASERA, vaca_id))
    print(f"[{i:2d}/{len(vacas)}] {vaca_id:4s}  ({n_fotos} fotos disponibles)  ", end="", flush=True)

    if n_fotos == 0:
        print("⚠ sin imágenes")
        errores.append({"vaca_id": vaca_id, "motivo": "sin imágenes"})
        continue

    try:
        r = medir_pt_rob_mejor(CARPETA_TRASERA, vaca_id, debug_dir=DEBUG_DIR)

        peso_r = float(df_pesos[df_pesos["vaca_id"]==vaca_id]["peso_real"].values[0])
        resultados.append({"vaca_id": vaca_id, "peso_real": peso_r, **{k:v for k,v in r.items() if not k.startswith("_")}})

        estado = "✓" if r["escala_ok"] else "⚠ foto pequeña"
        n_c = r.get("n_candidatos", 1)
        print(f"pt_rob={r['pt_rob']:.0f}cm  alt={r['alto_bbox_px']}px  "
              f"conf={r['confianza_rob']:.2f}  {estado}  "
              f"[{n_c} fotos OK → prom={r['pt_rob']:.0f}cm]")

    except Exception as e:
        print(f"❌ {e}")
        errores.append({"vaca_id": vaca_id, "motivo": str(e)})

# ── Guardar ───────────────────────────────────────────────────────
df_rob = pd.DataFrame(resultados)
df_rob.to_csv(str(OUTPUT_CSV), index=False)

print(f"\n{SEP}")
print(f"  RESUMEN")
print(f"{SEP}")
print(f"  Procesadas con éxito : {len(resultados)}")
print(f"  Con error            : {len(errores)}")
if errores:
    print(f"  Sin trasera válida   : {[e['vaca_id'] for e in errores]}")

if len(resultados) > 0:
    df_ok = df_rob[df_rob["escala_ok"]]
    print(f"\n  pt_rob promedio  : {df_rob['pt_rob'].mean():.1f} cm")
    print(f"  pt_rob min/max   : {df_rob['pt_rob'].min():.1f} / {df_rob['pt_rob'].max():.1f} cm")
    print(f"  Fotos escala OK  : {len(df_ok)}/{len(df_rob)} (alto_bbox ≥ 250px)")
    corr = df_rob["pt_rob"].corr(df_rob["peso_real"])
    print(f"  Corr pt_rob/peso : {corr:.3f}  (esperado ~0.80)")
    if corr >= 0.70:
        print(f"  ✅ Correlación buena — proceder con entrenar_modelos_rango.py")
    elif corr >= 0.50:
        print(f"  ⚠ Correlación moderada — puede funcionar, pero considera tomar fotos nuevas")
    else:
        print(f"  ❌ Correlación baja — las fotos disponibles son mayormente laterales")
        print(f"     Necesitas tomar fotos traseras estandarizadas (ver protocolo_fotos_traseras.docx)")

print(f"\n  Guardado: {OUTPUT_CSV}")
print(f"  Debug   : {DEBUG_DIR}/")
print(f"{SEP}\n")