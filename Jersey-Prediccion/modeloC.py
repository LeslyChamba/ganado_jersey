"""
entrenar_modelo_combinado.py — Regresión peso con features laterales + traseras
================================================================================
Combina lateral_features.csv  +  pt_rob_dataset.csv  →  entrena modelo de peso.

Estrategia para vacas sin foto trasera (pt_rob faltante):
  → Se imputa pt_rob con KNN-Imputer usando las features laterales.

Modelos probados:
  1. Random Forest Regressor
  2. Gradient Boosting (XGBoost-style con sklearn)
  3. Ridge Regression  (baseline lineal)

Salida:
  modelo_peso_combinado.pkl   ← modelo final
  scaler_peso.pkl             ← StandardScaler
  imputer_peso.pkl            ← KNNImputer para pt_rob
  resultados_cv.csv           ← métricas por fold
  predicciones_vs_real.png    ← gráfico diagnóstico

Uso:
  python entrenar_modelo_combinado.py

Requiere:
  pip install scikit-learn pandas numpy matplotlib joblib
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from pathlib import Path

from sklearn.ensemble          import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model      import Ridge
from sklearn.pipeline          import Pipeline
from sklearn.preprocessing     import StandardScaler
from sklearn.impute            import KNNImputer
from sklearn.model_selection   import KFold, cross_val_predict
from sklearn.metrics           import mean_absolute_error, r2_score, mean_squared_error

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
PROYECTO_DIR    = Path(r"C:\Users\HP\Documents\tesis_ganado_jersey\Jersey-Prediccion")
CSV_LATERAL     = PROYECTO_DIR / "lateral_features.csv"
CSV_TRASERA     = PROYECTO_DIR / "pt_rob_dataset.csv"
OUTPUT_MODELO   = PROYECTO_DIR / "modelo_peso_combinado.pkl"
OUTPUT_SCALER   = PROYECTO_DIR / "scaler_peso.pkl"
OUTPUT_IMPUTER  = PROYECTO_DIR / "imputer_peso.pkl"
OUTPUT_PLOT     = PROYECTO_DIR / "predicciones_vs_real.png"
OUTPUT_CV       = PROYECTO_DIR / "resultados_cv.csv"

SEED = 42


# ── CARGAR Y COMBINAR DATOS ───────────────────────────────────────────────────

df_lat  = pd.read_csv(str(CSV_LATERAL))
df_tras = pd.read_csv(str(CSV_TRASERA))[["vaca_id", "pt_rob"]]

# Merge: LEFT JOIN (conservar todas las vacas, pt_rob = NaN si no hay trasera)
df = df_lat.merge(df_tras, on="vaca_id", how="left")

print(f"\n{'═'*60}")
print(f"  Dataset combinado: {len(df)} vacas")
print(f"  Con pt_rob       : {df['pt_rob'].notna().sum()}")
print(f"  Sin pt_rob (NaN) : {df['pt_rob'].isna().sum()}  ← se imputarán")
print(f"{'═'*60}")

# ── FEATURES ──────────────────────────────────────────────────────────────────

# Features laterales (disponibles para todas las vacas)
FEATURES_LAT = [
    "largo_cm",
    "alzada_cm",
    "prof_tor_cm",
    "ratio_L_A",
    "ratio_PT_A",
]

# Feature trasera (puede tener NaN)
FEATURE_TRAS = ["pt_rob"]

ALL_FEATURES = FEATURES_LAT + FEATURE_TRAS
TARGET       = "peso_real"

X_raw = df[ALL_FEATURES].copy()
y     = df[TARGET].values

# ── IMPUTER para pt_rob faltante ──────────────────────────────────────────────
# KNN Imputer: estima pt_rob usando las 5 vacas más similares en features laterales
imputer = KNNImputer(n_neighbors=5, weights="distance")
X_imp   = imputer.fit_transform(X_raw)
X_imp   = pd.DataFrame(X_imp, columns=ALL_FEATURES)

print(f"\n  pt_rob imputado para {df['pt_rob'].isna().sum()} vacas:")
mask_imp = df["pt_rob"].isna()
for _, row in df[mask_imp].iterrows():
    idx = df.index.get_loc(_)
    pt_imp = X_imp.loc[idx, "pt_rob"]
    print(f"    {row['vaca_id']:6s}: pt_rob imputado = {pt_imp:.1f} cm")

# ── MODELOS ───────────────────────────────────────────────────────────────────

modelos = {
    "RandomForest": Pipeline([
        ("scaler", StandardScaler()),
        ("model",  RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=3,
            random_state=SEED
        ))
    ]),
    "GradientBoosting": Pipeline([
        ("scaler", StandardScaler()),
        ("model",  GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=3,
            subsample=0.8,
            random_state=SEED
        ))
    ]),
    "Ridge": Pipeline([
        ("scaler", StandardScaler()),
        ("model",  Ridge(alpha=1.0))
    ]),
}

# ── VALIDACIÓN CRUZADA ────────────────────────────────────────────────────────

cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
X_arr = X_imp[ALL_FEATURES].values

print(f"\n  {'Modelo':20s}  {'MAE':>8s}  {'RMSE':>8s}  {'R²':>7s}  {'MAE%':>7s}")
print(f"  {'─'*20}  {'─'*8}  {'─'*8}  {'─'*7}  {'─'*7}")

resultados_cv = []
mejor_mae     = float("inf")
mejor_modelo_nombre = None

for nombre, pipeline in modelos.items():
    y_pred = cross_val_predict(pipeline, X_arr, y, cv=cv)
    mae    = mean_absolute_error(y, y_pred)
    rmse   = np.sqrt(mean_squared_error(y, y_pred))
    r2     = r2_score(y, y_pred)
    mae_pct = mae / y.mean() * 100

    print(f"  {nombre:20s}  {mae:8.2f}  {rmse:8.2f}  {r2:7.3f}  {mae_pct:6.1f}%")
    resultados_cv.append({
        "modelo": nombre, "MAE_kg": round(mae,2), "RMSE_kg": round(rmse,2),
        "R2": round(r2,3), "MAE_pct": round(mae_pct,1)
    })

    if mae < mejor_mae:
        mejor_mae = mae
        mejor_modelo_nombre = nombre

# ── ENTRENAR MODELO FINAL ─────────────────────────────────────────────────────

print(f"\n  ✅ Mejor modelo: {mejor_modelo_nombre}  (MAE={mejor_mae:.2f} kg)")
modelo_final = modelos[mejor_modelo_nombre]
modelo_final.fit(X_arr, y)

# Guardar artefactos
joblib.dump(modelo_final, str(OUTPUT_MODELO))
joblib.dump(imputer,      str(OUTPUT_IMPUTER))

# Guardar importancia de features (solo para tree-based)
try:
    importancias = modelo_final.named_steps["model"].feature_importances_
    print(f"\n  Importancia de features ({mejor_modelo_nombre}):")
    for feat, imp in sorted(zip(ALL_FEATURES, importancias),
                             key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"    {feat:15s}: {imp:.3f}  {bar}")
except AttributeError:
    # Ridge no tiene feature_importances_
    coefs = modelo_final.named_steps["model"].coef_
    print(f"\n  Coeficientes ({mejor_modelo_nombre}):")
    for feat, coef in zip(ALL_FEATURES, coefs):
        print(f"    {feat:15s}: {coef:.3f}")

# Guardar CSV de resultados CV
pd.DataFrame(resultados_cv).to_csv(str(OUTPUT_CV), index=False)

# ── GRÁFICO DIAGNÓSTICO ───────────────────────────────────────────────────────

y_pred_final = cross_val_predict(modelo_final, X_arr, y, cv=cv)

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle(f"Modelo combinado (lateral + trasera) — {mejor_modelo_nombre}",
             fontsize=13, fontweight="bold")

# 1. Predicho vs Real
ax = axes[0]
ax.scatter(y, y_pred_final, alpha=0.7, edgecolors="k", linewidths=0.5,
           c="steelblue", s=60)
lim = [y.min()*0.9, y.max()*1.05]
ax.plot(lim, lim, "r--", lw=1.5, label="Ideal")
ax.set_xlabel("Peso real (kg)", fontsize=11)
ax.set_ylabel("Peso predicho (kg)", fontsize=11)
ax.set_title(f"Predicho vs Real\nMAE={mejor_mae:.1f} kg  R²={r2_score(y,y_pred_final):.3f}")
ax.legend(); ax.grid(alpha=0.3)

# Anotar vacas con error > 40 kg
for i, (vaca_id, yr, yp) in enumerate(zip(df["vaca_id"], y, y_pred_final)):
    if abs(yr - yp) > 40:
        ax.annotate(str(vaca_id), (yr, yp), fontsize=7, color="red",
                    xytext=(3, 3), textcoords="offset points")

# 2. Residuos
ax2 = axes[1]
residuos = y_pred_final - y
ax2.scatter(y_pred_final, residuos, alpha=0.7, edgecolors="k",
            linewidths=0.5, c="coral", s=60)
ax2.axhline(0, color="k", lw=1.5)
ax2.axhline( 2*residuos.std(), color="gray", lw=1, ls="--")
ax2.axhline(-2*residuos.std(), color="gray", lw=1, ls="--")
ax2.set_xlabel("Peso predicho (kg)"); ax2.set_ylabel("Residuo (kg)")
ax2.set_title("Residuos"); ax2.grid(alpha=0.3)

# 3. Comparación modelos
ax3 = axes[2]
nombres = [r["modelo"] for r in resultados_cv]
maes    = [r["MAE_kg"] for r in resultados_cv]
colors  = ["steelblue" if n == mejor_modelo_nombre else "lightgray" for n in nombres]
bars = ax3.bar(nombres, maes, color=colors, edgecolor="k")
ax3.set_ylabel("MAE (kg)"); ax3.set_title("Comparación modelos (CV 5-fold)")
ax3.bar_label(bars, fmt="%.1f", padding=3)
ax3.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(str(OUTPUT_PLOT), dpi=150, bbox_inches="tight")
plt.show()
print(f"\n  Gráfico guardado: {OUTPUT_PLOT}")

# ── REPORTE FINAL ─────────────────────────────────────────────────────────────

print(f"\n{'═'*60}")
print(f"  ARCHIVOS GENERADOS")
print(f"{'═'*60}")
print(f"  modelo_peso_combinado.pkl  ← cargar con joblib.load()")
print(f"  imputer_peso.pkl           ← para imputar pt_rob en producción")
print(f"  resultados_cv.csv          ← métricas para la tesis")
print(f"  predicciones_vs_real.png   ← gráfico para la tesis")
print(f"\n  CÓMO USAR EN PRODUCCIÓN:")
print(f"  ──────────────────────────")
print(f"  import joblib, numpy as np")
print(f"  modelo  = joblib.load('modelo_peso_combinado.pkl')")
print(f"  imputer = joblib.load('imputer_peso.pkl')")
print(f"")
print(f"  # Si tienes foto lateral + trasera:")
print(f"  X = np.array([[largo_cm, alzada_cm, prof_tor_cm,")
print(f"                 ratio_L_A, ratio_PT_A, pt_rob]])")
print(f"")
print(f"  # Si solo tienes foto lateral (pt_rob = NaN):")
print(f"  X = np.array([[largo_cm, alzada_cm, prof_tor_cm,")
print(f"                 ratio_L_A, ratio_PT_A, np.nan]])")
print(f"  X = imputer.transform(X)   # imputa pt_rob automáticamente")
print(f"")
print(f"  peso_kg = modelo.predict(X)[0]")
print(f"{'═'*60}\n")