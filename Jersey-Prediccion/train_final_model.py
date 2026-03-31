# train_final_model.py
"""
ENTRENAMIENTO DEL MODELO FINAL — BovineAI
==========================================
Ejecutar UNA VEZ después de validar con GroupKFold.
Entrena con TODOS los datos y guarda el modelo para el sistema web.

Uso:
    python train_final_model.py

Salida:
    models_pt/mass_model.json   ← este archivo usa el sistema web
    models_pt/feature_names.txt ← para verificar el orden de features
"""

import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from pathlib import Path


# ══════════════════════════════════════════════════════════
# 1. CARGAR Y FILTRAR DATOS
# ══════════════════════════════════════════════════════════

df = pd.read_csv("features_imagenes.csv")

conteo = df.groupby("vaca_id").size()
vacas_validas = conteo[conteo >= 10].index
df = df[df["vaca_id"].isin(vacas_validas)]

pesos = pd.read_csv("pesos_vacas.csv", sep=";", decimal=",")
df = df.merge(pesos, on="vaca_id")

print(f"Vacas: {df['vaca_id'].nunique()} | Imágenes: {len(df)}")


# ══════════════════════════════════════════════════════════
# 2. FEATURES (mismo orden que en el sistema web)
# ══════════════════════════════════════════════════════════

df["perimeter_norm"] = df["perimeter"] / df["height"]
df["volumen_aprox"]  = (df["pt"] ** 2) * df["lc"]

FEATURES = [
    "area_norm",
    "ratio_lh",
    "perimeter_norm",
    "bcs",
    "pt",
    "lc",
    "volumen_aprox",
]

X      = df[FEATURES].values
y      = df["peso_cinta"].values
groups = df["vaca_id"].values

print(f"\nFeatures ({len(FEATURES)}): {FEATURES}")
print(f"Target: peso_cinta | Media: {y.mean():.1f} kg | Std: {y.std():.1f} kg")


# ══════════════════════════════════════════════════════════
# 3. VALIDACIÓN CRUZADA (reproducción del experimento)
# ══════════════════════════════════════════════════════════

print("\n── Validación GroupKFold (5 folds) ──")
gkf = GroupKFold(n_splits=5)
mae_scores = []

for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups), 1):
    m = XGBRegressor(
        n_estimators=500, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    m.fit(X[train_idx], y[train_idx])
    preds = m.predict(X[test_idx])

    fold_df = df.iloc[test_idx].copy()
    fold_df["pred"] = preds
    vaca_pred = fold_df.groupby("vaca_id")["pred"].mean()
    vaca_real = fold_df.groupby("vaca_id")["peso_cinta"].first()
    mae = mean_absolute_error(vaca_real, vaca_pred)
    mae_scores.append(mae)
    print(f"  Fold {fold}: MAE = {mae:.2f} kg")

mae_mean = np.mean(mae_scores)
mae_std  = np.std(mae_scores)
mae_rel  = mae_mean / np.mean(y) * 100

print(f"\n  MAE promedio : {mae_mean:.2f} ± {mae_std:.2f} kg")
print(f"  MAE relativo : {mae_rel:.1f}% del peso promedio")
print(f"  Peso promedio: {np.mean(y):.1f} kg")

if mae_rel <= 8.0:
    print("  ✓ Error dentro del umbral aceptable (≤8%)")
else:
    print("  ⚠ Error por encima del umbral. Considera ajustar hiperparámetros.")


# ══════════════════════════════════════════════════════════
# 4. MODELO FINAL — entrena con TODOS los datos
# ══════════════════════════════════════════════════════════

print("\n── Entrenando modelo final con todos los datos ──")
model_final = XGBRegressor(
    n_estimators=500, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, random_state=42
)
model_final.fit(X, y)

# ══════════════════════════════════════════════════════════
# 5. GUARDAR MODELO
# ══════════════════════════════════════════════════════════

Path("models_pt").mkdir(exist_ok=True)
model_path = "models_pt/mass_model.json"
model_final.save_model(model_path)
print(f"  ✓ Modelo guardado en: {model_path}")

# Guardar orden de features (crítico para que el sistema web use el mismo orden)
features_path = "models_pt/feature_names.txt"
with open(features_path, "w") as f:
    f.write("\n".join(FEATURES))
print(f"  ✓ Features guardadas en: {features_path}")


# ══════════════════════════════════════════════════════════
# 6. IMPORTANCIA DE FEATURES
# ══════════════════════════════════════════════════════════

print("\n── Importancia de features ──")
importances = model_final.feature_importances_
for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
    bar = "█" * int(imp * 40)
    print(f"  {feat:<20} {bar} {imp:.4f}")

print("\n✓ Listo. Ahora puedes iniciar el sistema web con:")
print("  uvicorn main:app --reload --port 8000")
