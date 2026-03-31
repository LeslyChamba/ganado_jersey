"""
JER-WEIGHT — Entrenamiento mass_model.json  v6
===============================================
Mejoras sobre v5:

1. ratio_lh NORMALIZADO (siempre >= 1)
   En el dataset 62/67 vacas tienen ratio_lh < 1 porque SAM las detecta
   verticales. En producción se invertía solo cuando ángulo>45°.
   Inconsistencia → ahora SIEMPRE se normaliza: ratio_lh = max(r, 1/r)

2. Augmentación más agresiva para extremos
   <380 kg: ×5  (era ×3)
   >580 kg: ×5  (era ×3)
   BCS≥4.0 con peso<400: ×8  (caso más problemático)

3. Sample weights más agresivos
   <380 o >580 kg: 6.0  (era 4.0)
   BCS≥4.0 con peso<400: 10.0

4. Hiperparámetros ajustados
   max_depth=3, min_child_weight=3, n_estimators=600
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor
import os, json

CSV_FEATURES   = "features_imagenes.csv"
OUTPUT_DIR     = "models_pt"
CONFIDENCE_MIN = 0.40

# ── Constantes IDÉNTICAS a probar_imagen.py ───────────────────────
LC_FACTOR_POR_RANGO = [
    (0,    70,  2.539),
    (70,   100, 1.803),
    (100,  130, 1.400),
    (130,  999, 1.070),
]
BCS_PT_ANCHOR  = {3.00:179.0, 3.25:178.0, 3.50:181.0, 4.00:189.0, 4.50:197.0}
PT_IMG_MEDIAN  = 185.0
PT_IMG_ESCALA  = 0.338
LC_REAL_CONST  = 160.0

FEATURES = [
    "ratio_lh",   # ← normalizado (siempre >= 1) — CAMBIO v6
    "htor_norm",
    "cad_norm",
    "perim_norm",
    "area_norm",
    "bcs",
    "pt_img",
    "lc_img",     # × factor_dinámico
    "vol_img",
    "pt_real",    # BCS anchor
    "lc_real",    # 160.0
    "vol_real",
]

bins   = [200, 380, 500, 580, 750]
labels = ["<380 kg", "380-500 kg", "500-580 kg", ">580 kg"]


def get_lc_factor(lc_cm):
    for lo, hi, factor in LC_FACTOR_POR_RANGO:
        if lo <= lc_cm < hi:
            return factor
    return 1.070


def get_pt_real_est(pt_img, bcs):
    bcs_key = round(bcs * 4) / 4
    anchor  = BCS_PT_ANCHOR.get(bcs_key, 180.0)
    return float(np.clip(anchor + (pt_img - PT_IMG_MEDIAN)*PT_IMG_ESCALA, 155.0, 205.0))


def normalizar_ratio_lh(r):
    """Siempre retorna ratio >= 1. Consistente con producción."""
    if r <= 0: return 1.0
    return max(r, 1.0 / r)


# ── 1. Cargar datos ────────────────────────────────────────────────
df = pd.read_csv(CSV_FEATURES)
print(f"CSV: {len(df)} filas\n")

df = df.dropna(subset=["pt_img","lc_img","peso_real","bcs","ratio_lh"])
df = df[(df["pt_img"] > 0) & (df["lc_img"] > 0)]
df = df[df["confidence"] >= CONFIDENCE_MIN]

for col in ["pt_img","lc_img"]:
    q1, q99 = df[col].quantile(0.01), df[col].quantile(0.99)
    df = df[(df[col] >= q1) & (df[col] <= q99)]

print(f"Tras filtros: {len(df)} imágenes")

# ── 2. Calcular features de producción ────────────────────────────
pt_v  = df["pt_img"].values
lc_v  = df["lc_img"].values
bcs_v = df["bcs"].values
rl_v  = df["ratio_lh"].values

lc_factor_v   = np.array([get_lc_factor(v) for v in lc_v])
lc_prod_v     = lc_v * lc_factor_v
pt_real_v     = np.array([get_pt_real_est(p, b) for p, b in zip(pt_v, bcs_v)])
ratio_lh_norm = np.array([normalizar_ratio_lh(r) for r in rl_v])  # ← NUEVO v6
vol_img_v     = pt_v**2 * lc_prod_v
vol_real_v    = pt_real_v**2 * LC_REAL_CONST

df = df.copy()
df["ratio_lh"] = ratio_lh_norm    # sobreescribir con versión normalizada
df["lc_img"]   = lc_prod_v
df["pt_real"]  = pt_real_v
df["lc_real"]  = LC_REAL_CONST
df["vol_img"]  = vol_img_v
df["vol_real"] = vol_real_v

# Filtro mínimo 5 imágenes por vaca
conteo   = df.groupby("vaca_id").size()
vacas_ok = conteo[conteo >= 5].index
df       = df[df["vaca_id"].isin(vacas_ok)].reset_index(drop=True)

print(f"Vacas: {df['vaca_id'].nunique()} | Imágenes: {len(df)}")
print(f"Rango pesos: {df['peso_real'].min():.0f}–{df['peso_real'].max():.0f} kg")

df["rango"] = pd.cut(df["peso_real"], bins=bins, labels=labels)
print("\nImágenes por rango:")
print(df["rango"].value_counts().sort_index())

# ── 3. Augmentación conservadora ─────────────────────────────────
# ×8 para BCS-liviano sobreajustó → predijo 600kg para vacas de 300kg
# Volvemos a ×3 conservador, manteniendo solo el ratio_lh normalizado
np.random.seed(42)

idx_ext = df[(df["peso_real"] < 380) | (df["peso_real"] > 580)].index
idx_med = df[(df["peso_real"] >= 500) & (df["peso_real"] < 580)].index

GEO_COLS = ["ratio_lh","perim_norm","area_norm","htor_norm","cad_norm","pt_img"]
aug_rows = []

def augmentar(sub_df, n_reps, noise_std):
    rows = []
    for _ in range(n_reps):
        row = sub_df.copy().reset_index(drop=True)
        for col in GEO_COLS:
            noise    = np.random.normal(0, noise_std, len(row))
            row[col] = (row[col].values * (1 + noise)).clip(min=0.001)
        row["ratio_lh"] = row["ratio_lh"].apply(normalizar_ratio_lh)
        pt_a  = row["pt_img"].values
        lc_a  = row["lc_img"].values
        bcs_a = row["bcs"].values
        pt_r  = np.array([get_pt_real_est(p, b) for p, b in zip(pt_a, bcs_a)])
        row["pt_real"]  = pt_r
        row["vol_img"]  = pt_a**2 * lc_a
        row["vol_real"] = pt_r**2 * LC_REAL_CONST
        rows.append(row)
    return rows

# Extremos ×3 (conservador — igual que v5)
aug_rows += augmentar(df.loc[idx_ext], 3, 0.05)
# Medios ×1
aug_rows += augmentar(df.loc[idx_med], 1, 0.04)

df_aug = pd.concat([df] + aug_rows, ignore_index=True)
print(f"\nDataset original  : {len(df)}")
print(f"Con augmentación  : {len(df_aug)}")

# ── 4. Features, target, pesos ────────────────────────────────────
X      = df_aug[FEATURES].values.astype(np.float32)
y      = df_aug["peso_real"].values.astype(np.float32)
groups = df_aug["vaca_id"].values

# Sample weights conservadores (4.0 para extremos — igual que v5)
sw = np.ones(len(y))
sw[(y < 380) | (y > 580)] = 4.0

print(f"\nSample weights:")
print(f"  4.0 extremos : {(sw==4.0).sum()}")
print(f"  1.0 central  : {(sw==1.0).sum()}")

# ── 5. Hiperparámetros v6b (conservadores como v5) ────────────────
PARAMS = dict(
    n_estimators     = 400,
    max_depth        = 4,
    learning_rate    = 0.03,
    subsample        = 0.8,
    colsample_bytree = 0.7,
    min_child_weight = 5,
    reg_alpha        = 0.1,
    reg_lambda       = 1.0,
    random_state     = 42,
)

# ── 6. Validación cruzada ─────────────────────────────────────────
gkf        = GroupKFold(n_splits=5)
mae_scores = []
mae_rango  = {r: [] for r in labels}

print("\n─── Validación cruzada GroupKFold (5 folds) ───")
for fold, (tr, te) in enumerate(gkf.split(X, y, groups), 1):
    m = XGBRegressor(**PARAMS)
    m.fit(X[tr], y[tr], sample_weight=sw[tr])
    preds    = m.predict(X[te])
    fold_df  = pd.DataFrame({"id":groups[te],"pred":preds,"real":y[te]})
    vp       = fold_df.groupby("id")["pred"].mean()
    vr       = fold_df.groupby("id")["real"].first()
    mae      = mean_absolute_error(vr, vp)
    mae_scores.append(mae)
    for v in vr.index:
        pr = float(vr[v]); pp = float(vp[v])
        for lo, hi, lbl in zip(bins[:-1], bins[1:], labels):
            if lo <= pr < hi:
                mae_rango[lbl].append(abs(pr - pp))
    print(f"  Fold {fold}  MAE: {mae:.2f} kg")

print(f"\n  MAE promedio : {np.mean(mae_scores):.2f} kg")
print(f"  MAE por rango:")
for lbl, errs in mae_rango.items():
    if errs:
        print(f"    {lbl:12s} → {np.mean(errs):.1f} kg  (n={len(errs)})")

# ── 7. Modelo final ────────────────────────────────────────────────
print("\n─── Entrenando modelo final ───")
model_final = XGBRegressor(**PARAMS)
model_final.fit(X, y, sample_weight=sw)

print("\nImportancia de features:")
for feat, imp in sorted(zip(FEATURES, model_final.feature_importances_), key=lambda x:-x[1]):
    bar = "█" * int(imp * 40)
    print(f"  {feat:15s}: {imp:.4f}  {bar}")

# ── 8. Guardar ────────────────────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
model_final.save_model(f"{OUTPUT_DIR}/mass_model.json")

with open(f"{OUTPUT_DIR}/feature_names.txt", "w") as f:
    f.write("\n".join(FEATURES))

resumen = {
    "version"        : "v6b",
    "features"       : FEATURES,
    "n_features"     : len(FEATURES),
    "notas"          : [
        "ratio_lh normalizado siempre >= 1 — único cambio vs v5",
        "augmentacion extremos x3 conservador",
        "sample_weight extremos=4.0",
        "hiperparametros identicos a v5",
    ],
    "mae_promedio"   : round(float(np.mean(mae_scores)), 2),
    "mae_por_fold"   : [round(float(x), 2) for x in mae_scores],
    "mae_por_rango"  : {k: round(float(np.mean(v)), 2) for k,v in mae_rango.items() if v},
    "n_vacas"        : int(df["vaca_id"].nunique()),
    "hiperparametros": PARAMS,
}
with open(f"{OUTPUT_DIR}/training_summary.json","w") as f:
    json.dump(resumen, f, indent=2)

print(f"\n✓ mass_model.json  ✓ feature_names.txt  ✓ training_summary.json")
print(f"\n{'='*50}")
print(f"RESUMEN FINAL — v6")
print(f"{'='*50}")
print(f"MAE promedio : {np.mean(mae_scores):.2f} kg")
for lbl, errs in mae_rango.items():
    if errs:
        print(f"  {lbl:12s} → {np.mean(errs):.1f} kg")