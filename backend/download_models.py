"""
download_models.py
Descarga los pesos de los modelos que NO están en el repositorio de GitHub.
Se ejecuta una sola vez durante el Build de Render.

Build Command en Render:
    pip install -r requirements.txt && python download_models.py
"""
import os
from pathlib import Path

MODELS_DIR     = Path("models_pt")
MODELS_DIR_CNN = MODELS_DIR / "models_ptA"
MODELS_DIR.mkdir(exist_ok=True)
MODELS_DIR_CNN.mkdir(exist_ok=True)

HF_TOKEN = os.getenv("HF_TOKEN")  # variable de entorno en Render

def descargar_si_falta(repo_id: str, filename: str, destino: Path):
    if destino.exists():
        print(f"  ✓ Ya existe: {destino}")
        return
    print(f"  ⬇ Descargando {filename} desde {repo_id}...")
    from huggingface_hub import hf_hub_download
    ruta_tmp = hf_hub_download(repo_id=repo_id, filename=filename, token=HF_TOKEN)
    import shutil
    shutil.copy(ruta_tmp, destino)
    print(f"  ✓ Guardado en {destino}")

def descargar_mobile_sam():
    destino = MODELS_DIR / "mobile_sam.pt"
    if destino.exists():
        print(f"  ✓ Ya existe: {destino}")
        return
    print("  ⬇ Descargando mobile_sam.pt desde HuggingFace...")
    import urllib.request
    url = "https://huggingface.co/dhkim2810/MobileSAM/resolve/main/mobile_sam.pt"
    urllib.request.urlretrieve(url, destino)
    print(f"  ✓ Guardado en {destino} ({destino.stat().st_size / 1024**2:.1f} MB)")

if __name__ == "__main__":
    print("\n=== JER-WEIGHT — Descarga de modelos ===\n")

    # 1. MobileSAM weights (~9 MB)
    print("[ MobileSAM ]")
    descargar_mobile_sam()

    # 2. Modelos desde tu Hugging Face privado
    REPO = "lesly15/Peso"
    print(f"\n[ Modelos desde HF: {REPO} ]")
    descargar_si_falta(REPO, "best.pt",              MODELS_DIR / "best.pt")
    descargar_si_falta(REPO, "mass_model_v3.json",   MODELS_DIR / "mass_model_v3.json")
    descargar_si_falta(REPO, "feature_names_v3.txt", MODELS_DIR / "feature_names_v3.txt")

    # 3. CNN folds (~18.7 MB cada uno)
    print(f"\n[ CNN folds desde HF: {REPO} ]")
    for i in range(1, 6):
        descargar_si_falta(
            REPO,
            f"hibrido_fold_{i}.pth",
            MODELS_DIR_CNN / f"hibrido_fold_{i}.pth"
        )

    print("\n=== Descarga completada ===\n")