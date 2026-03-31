# entrenar_modelo.py
"""
BovineAI — Reentrenamiento XGBoost v2
Usa features relativas (invariantes a distancia/escala) + medidas reales
como features directas cuando están disponibles.

Uso:
  python entrenar_modelo.py
  python entrenar_modelo.py --features mis_features.csv
"""

import argparse
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

# ── Rutas ─────────────────────────────────────────────────
PROYECTO_DIR   = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
FEATURES_DEF   = PROYECTO_DIR / "features_imagenes.csv"
MODELO_SALIDA  = PROYECTO_DIR / "models_pt" / "mass_model.json"
REPORTE_SALIDA = PROYECTO_DIR / "reporte_entrenamiento.png"

parser = argparse.ArgumentParser()
parser.add_argument("--features",  default=str(FEATURES_DEF))
parser.add_argument("--modelo",    default=str(MODELO_SALIDA))
parser.add_argument("--min_imgs",  type=int, default=5)
args = parser.parse_args()

SEP = "═" * 62
print(f"\n{SEP}")
print("  BovineAI — Reentrenamiento XGBoost v2")
print(f"{SEP}\n")


# ══════════════════════════════════════════════════════════
# 1. CARGAR Y LIMPIAR
# ══════════════════════════════════════════════════════════

df = pd.read_csv(args.features)
print(f"[ 1/5 ] Features cargadas: {len(df)} filas, {df['vaca_id'].nunique()} vacas")

# Necesitamos peso_real
if "peso_real" not in df.columns:
    raise ValueError("El CSV no tiene columna 'peso_real'. Revisa medidas_fisicas.csv")

df = df.dropna(subset=["peso_real"])

# Filtrar vacas con pocas imágenes
conteo    = df.groupby("vaca_id").size()
vacas_ok  = conteo[conteo >= args.min_imgs].index
df        = df[df["vaca_id"].isin(vacas_ok)].copy()
print(f"        Tras filtro (≥{args.min_imgs} imgs): {len(df)} filas, {df['vaca_id'].nunique()} vacas")

# Eliminar outliers de features relativas por IQR
for col in ["ratio_lh", "htor_norm", "perim_norm"]:
    if col not in df.columns: continue
    q1, q3 = df[col].quantile(0.05), df[col].quantile(0.95)
    iqr = q3 - q1
    antes = len(df)
    df = df[(df[col] >= q1-1.5*iqr) & (df[col] <= q3+1.5*iqr)]
    eliminados = antes - len(df)
    if eliminados > 0:
        print(f"        Outliers en '{col}': {eliminados} filas eliminadas")

print()


# ══════════════════════════════════════════════════════════
# 2. CONSTRUIR FEATURES
# Estrategia:
#   A) Features relativas de imagen (siempre disponibles, robustas)
#   B) Medidas reales de cinta (si están disponibles) → más precisas
#   C) BCS anotado manualmente
# ══════════════════════════════════════════════════════════

# BCS: rellenar vacíos con 3.25
df["bcs"] = pd.to_numeric(df["bcs"], errors="coerce").fillna(3.25)

# Determinar qué medidas reales tenemos
tiene_lc_real = "lc_real" in df.columns and df["lc_real"].notna().mean() > 0.5
tiene_pt_real = "pt_real" in df.columns and df["pt_real"].notna().mean() > 0.5
tiene_ac_real = "ac_real" in df.columns and df["ac_real"].notna().mean() > 0.5

print(f"[ 2/5 ] Medidas reales disponibles:")
print(f"        LC real : {'✓' if tiene_lc_real else '✗'}")
print(f"        PT real : {'✓' if tiene_pt_real else '✗'}")
print(f"        AC real : {'✓' if tiene_ac_real else '✗'}")

# ── Volumen alométrico ────────────────────────────────────
# Preferir medidas reales; fallback a estimación desde imagen
if tiene_pt_real and tiene_lc_real:
    df["pt_uso"] = df["pt_real"]
    df["lc_uso"] = df["lc_real"]
    print("        Volumen alométrico: PT_real × LC_real  ✓")
else:
    df["pt_uso"] = df["pt_img"]
    df["lc_uso"] = df["lc_img"]
    print("        Volumen alométrico: PT_img × LC_img (estimado)")

df["volumen"] = (df["pt_uso"]**2) * df["lc_uso"]

# ── Definir conjunto de features ─────────────────────────
FEATURES_BASE = [
    # Relativas (invariantes a distancia de cámara)
    "ratio_lh",      # largo/alto de la silueta
    "htor_norm",     # altura tórax / altura vaca
    "cad_norm",      # altura cadera normalizada
    "perim_norm",    # perímetro / altura
    "area_norm",     # área silueta / área imagen
    # Condición corporal
    "bcs",
    # Volumen alométrico (PT²×LC)
    "volumen",
]

# Añadir medidas reales de cinta si están disponibles
# (pt_real y lc_real son las más importantes; ac_real es opcional)
if tiene_lc_real: FEATURES_BASE.append("lc_real")
if tiene_pt_real: FEATURES_BASE.append("pt_real")
# ac_real no incluida (no disponible en este dataset)

# Verificar que todas existen
faltantes = [f for f in FEATURES_BASE if f not in df.columns]
if faltantes:
    raise ValueError(f"Columnas faltantes: {faltantes}")

print(f"\n        Features usadas ({len(FEATURES_BASE)}):")
for f in FEATURES_BASE:
    print(f"          · {f}")

X      = df[FEATURES_BASE].values.astype(np.float32)
y      = df["peso_real"].values.astype(np.float32)
groups = df["vaca_id"].values

print(f"\n        Peso real: min={y.min():.0f}  max={y.max():.0f}  "
      f"media={y.mean():.0f}  std={y.std():.0f} kg")
print()


# ══════════════════════════════════════════════════════════
# 3. VALIDACIÓN CRUZADA GroupKFold
# ══════════════════════════════════════════════════════════

n_vacas = df["vaca_id"].nunique()
n_folds = min(5, n_vacas)
gkf     = GroupKFold(n_splits=n_folds)

print(f"[ 3/5 ] Validación cruzada ({n_folds} folds GroupKFold)...")
print(f"        Cada vaca aparece SOLO en train o SOLO en test")
print()

mae_scores = []
r2_scores  = []
todas_preds = []

for fold, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups), 1):
    model = xgb.XGBRegressor(
        n_estimators=600, max_depth=4, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.8,
        min_child_weight=3, gamma=0.1,
        reg_alpha=0.5, reg_lambda=1.0,
        random_state=42, verbosity=0,
    )
    model.fit(X[tr_idx], y[tr_idx],
              eval_set=[(X[te_idx], y[te_idx])], verbose=False)

    preds   = model.predict(X[te_idx])
    fold_df = df.iloc[te_idx][["vaca_id","peso_real"]].copy()
    fold_df["pred"] = preds

    vaca_pred = fold_df.groupby("vaca_id")["pred"].mean()
    vaca_real = fold_df.groupby("vaca_id")["peso_real"].first()

    mae = mean_absolute_error(vaca_real, vaca_pred)
    r2  = r2_score(vaca_real, vaca_pred) if len(vaca_real) > 1 else float("nan")
    mae_scores.append(mae)
    r2_scores.append(r2)

    print(f"  Fold {fold}/{n_folds}  MAE:{mae:6.1f} kg  R²:{r2:.3f}  "
          f"({len(vaca_real)} vacas en test)")
    for vid in vaca_real.index:
        err = vaca_pred[vid] - vaca_real[vid]
        print(f"    {vid:<8} real:{vaca_real[vid]:.0f}  pred:{vaca_pred[vid]:.0f}  "
              f"err:{err:+.0f} kg")
        todas_preds.append({"vaca_id":vid, "real":float(vaca_real[vid]),
                            "pred":float(vaca_pred[vid]), "error":float(err), "fold":fold})
    print()

print(f"  {'─'*40}")
print(f"  MAE promedio : {np.mean(mae_scores):.1f} ± {np.std(mae_scores):.1f} kg")
print(f"  R²  promedio : {np.nanmean(r2_scores):.3f}")
print()


# ══════════════════════════════════════════════════════════
# 4. MODELO FINAL (todos los datos)
# ══════════════════════════════════════════════════════════

print(f"[ 4/5 ] Entrenando modelo final...")
modelo_final = xgb.XGBRegressor(
    n_estimators=700, max_depth=4, learning_rate=0.03,
    subsample=0.8, colsample_bytree=0.8,
    min_child_weight=3, gamma=0.1,
    reg_alpha=0.5, reg_lambda=1.0,
    random_state=42, verbosity=0,
)
modelo_final.fit(X, y)

Path(args.modelo).parent.mkdir(parents=True, exist_ok=True)
modelo_final.get_booster().save_model(args.modelo)
print(f"        Modelo guardado: {args.modelo}\n")

imp = modelo_final.feature_importances_
print("        Importancia de features:")
for feat, v in sorted(zip(FEATURES_BASE, imp), key=lambda x:-x[1]):
    print(f"          {'█'*int(v*40):<40} {v:.3f}  {feat}")


# ══════════════════════════════════════════════════════════
# 5. GUARDAR METADATA DEL MODELO
# ══════════════════════════════════════════════════════════

meta_path = Path(args.modelo).with_suffix(".meta.txt")
with open(meta_path, "w") as f:
    f.write(f"features={','.join(FEATURES_BASE)}\n")
    f.write(f"lc_real={tiene_lc_real}\n")
    f.write(f"pt_real={tiene_pt_real}\n")
    f.write(f"mae_cv={np.mean(mae_scores):.2f}\n")
    f.write(f"r2_cv={np.nanmean(r2_scores):.3f}\n")
print(f"[ 5/5 ] Metadata guardada: {meta_path}\n")


# ══════════════════════════════════════════════════════════
# REPORTE GRÁFICO
# ══════════════════════════════════════════════════════════

preds_df = pd.DataFrame(todas_preds)
fig, axes = plt.subplots(1, 3, figsize=(17, 5))
fig.suptitle("BovineAI — Reporte Reentrenamiento XGBoost v2", fontsize=13, fontweight="bold")

# Real vs Predicho
ax = axes[0]
ax.scatter(preds_df["real"], preds_df["pred"], s=70, alpha=0.8, edgecolors="k", lw=0.5)
lim = [preds_df["real"].min()-20, preds_df["real"].max()+20]
ax.plot(lim, lim, "r--", lw=1.5, label="Ideal")
ax.fill_between(lim, [l-20 for l in lim], [l+20 for l in lim], alpha=0.1, color="green", label="±20 kg")
ax.set_xlabel("Peso real (kg)"); ax.set_ylabel("Peso predicho (kg)")
ax.set_title("Real vs Predicho (por vaca)"); ax.legend(); ax.set_xlim(lim); ax.set_ylim(lim)
for _, row in preds_df.iterrows():
    ax.annotate(row["vaca_id"], (row["real"], row["pred"]), fontsize=7, alpha=0.6,
                textcoords="offset points", xytext=(4,2))

# Error por vaca
ax = axes[1]
colores = ["#2ecc71" if abs(e)<=20 else "#f39c12" if abs(e)<=40 else "#e74c3c"
           for e in preds_df["error"]]
ax.bar(preds_df["vaca_id"], preds_df["error"], color=colores, edgecolor="k", lw=0.5)
ax.axhline(0, color="k", lw=1)
for lv, lc, la in [(20,"#2ecc71","±20 kg"),(40,"#f39c12","±40 kg")]:
    ax.axhline(lv, color=lc, lw=1, ls="--", alpha=0.7, label=la)
    ax.axhline(-lv, color=lc, lw=1, ls="--", alpha=0.7)
ax.set_xlabel("Vaca ID"); ax.set_ylabel("Error (pred−real) kg")
ax.set_title("Error por vaca"); ax.legend(fontsize=8)
plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
ax.text(0.02, 0.98, f"MAE={np.mean(mae_scores):.1f} kg", transform=ax.transAxes,
        va="top", fontsize=10, color="navy")

# Importancia features
ax = axes[2]
feat_imp = sorted(zip(FEATURES_BASE, imp), key=lambda x:x[1])
ax.barh([f[0] for f in feat_imp], [f[1] for f in feat_imp],
        color="steelblue", edgecolor="k", lw=0.5)
ax.set_xlabel("Importancia"); ax.set_title("Importancia de features")

plt.tight_layout()
fig.savefig(str(REPORTE_SALIDA), dpi=130, bbox_inches="tight")
print(f"  Reporte gráfico: {REPORTE_SALIDA}")

# ── Resumen ───────────────────────────────────────────────
mae_prom = np.mean(mae_scores)
calidad  = ("✓ EXCELENTE  (<20 kg)"  if mae_prom<=20 else
            "✓ BUENO      (<35 kg)"  if mae_prom<=35 else
            "⚠ ACEPTABLE  (<50 kg)"  if mae_prom<=50 else
            "✗ MEJORABLE  (>50 kg)")
print(f"\n{SEP}")
print("  RESUMEN FINAL")
print(f"{SEP}")
print(f"  Vacas entrenadas : {df['vaca_id'].nunique()}")
print(f"  Imágenes usadas  : {len(df)}")
print(f"  MAE CV           : {mae_prom:.1f} ± {np.std(mae_scores):.1f} kg")
print(f"  R² CV            : {np.nanmean(r2_scores):.3f}")
print(f"  Calidad          : {calidad}")
print(f"  Modelo           : {args.modelo}")
print(f"{SEP}\n")
