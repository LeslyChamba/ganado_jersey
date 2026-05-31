import logging
import os
from pathlib import Path

logger = logging.getLogger("jer-weight.models")

# Ruta fija para MobileSAM (no viene de settings porque es nuevo)
MOBILE_SAM_PATH = Path("models_pt/mobile_sam.pt")
MOBILE_SAM_URL  = "https://huggingface.co/dhkim2810/MobileSAM/resolve/main/mobile_sam.pt"


def descargar_modelos():
    try:
        from huggingface_hub import hf_hub_download
        from app.core.config import settings
    except ImportError:
        logger.warning("⚠️  huggingface_hub no instalado — omitiendo descarga de modelos")
        return

    # ── 1. MobileSAM weights (repo público, no necesita token) ───────────────
    if MOBILE_SAM_PATH.exists():
        logger.info(f"✅ MobileSAM ya existe: {MOBILE_SAM_PATH}")
    else:
        MOBILE_SAM_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"⬇️  Descargando mobile_sam.pt → {MOBILE_SAM_PATH}")
        try:
            import urllib.request
            urllib.request.urlretrieve(MOBILE_SAM_URL, MOBILE_SAM_PATH)
            logger.info(f"✅ mobile_sam.pt listo ({MOBILE_SAM_PATH.stat().st_size / 1024**2:.1f} MB)")
        except Exception as e:
            logger.error(f"❌ Error descargando mobile_sam.pt: {e}")
            raise RuntimeError("No se pudo descargar mobile_sam.pt") from e

    # ── 2. Modelos privados desde tu HuggingFace ─────────────────────────────
    if not settings.HF_REPO_ID or not settings.HF_TOKEN:
        logger.info("ℹ️  HF_REPO_ID/HF_TOKEN no configurados — usando modelos locales")
        return

    # ELIMINADO: sam_vit_b.pth (~375 MB) — reemplazado por MobileSAM arriba
    MODELOS = {
        "best.pt":     settings.MASS_MODEL_PATH,   # models_pt/Peso/best.pt
        "best_BCS.pt": settings.BCS_MODEL_PATH,    # models_pt/BCS/best_BCS.pt
    }

    for hf_filename, local_path in MODELOS.items():
        local = Path(local_path)

        if local.exists():
            logger.info(f"✅ {hf_filename} ya existe: {local_path}")
            continue

        local.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"⬇️  Descargando {hf_filename} → {local_path}")
        try:
            downloaded = hf_hub_download(
                repo_id=settings.HF_REPO_ID,
                filename=hf_filename,
                token=settings.HF_TOKEN or None,
                local_dir=str(local.parent),
            )
            downloaded_path = Path(downloaded)
            if downloaded_path != local:
                downloaded_path.rename(local)
            logger.info(f"✅ {hf_filename} listo en {local_path}")
        except Exception as e:
            logger.error(f"❌ Error descargando {hf_filename}: {e}")
            raise RuntimeError(f"No se pudo descargar {hf_filename}") from e