import logging
import os
from pathlib import Path

logger = logging.getLogger("jer-weight.models")


def descargar_modelos():
    try:
        from huggingface_hub import hf_hub_download
        from app.core.config import settings
    except ImportError:
        logger.warning("⚠️  huggingface_hub no instalado — omitiendo descarga de modelos")
        return

    if not settings.HF_REPO_ID or not settings.HF_TOKEN:
        logger.info("ℹ️  HF_REPO_ID/HF_TOKEN no configurados — usando modelos locales")
        return

    # filename en HF → ruta local esperada por settings
    MODELOS = {
        "best.pt":       settings.MASS_MODEL_PATH,    # models_pt/Peso/best.pt
        "best_BCS.pt":   settings.BCS_MODEL_PATH,     # models_pt/BCS/best_BCS.pt
        "sam_vit_b.pth": settings.SAM_CHECKPOINT_PATH, # models_pt/sam_checkpoint.pth
    }

    for hf_filename, local_path in MODELOS.items():
        local = Path(local_path)

        if local.exists():
            logger.info(f"✅ Modelo ya existe: {local_path}")
            continue

        # Crear carpeta destino si no existe
        local.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"⬇️  Descargando {hf_filename} → {local_path}")
        try:
            downloaded = hf_hub_download(
                repo_id=settings.HF_REPO_ID,
                filename=hf_filename,
                token=settings.HF_TOKEN or None,
                local_dir=str(local.parent),  # descarga en la carpeta correcta
            )
            # hf_hub_download puede crear subcarpetas propias, renombrar si es necesario
            downloaded_path = Path(downloaded)
            if downloaded_path != local:
                downloaded_path.rename(local)

            logger.info(f"✅ {hf_filename} listo en {local_path}")
        except Exception as e:
            logger.error(f"❌ Error descargando {hf_filename}: {e}")
            raise RuntimeError(f"No se pudo descargar {hf_filename}") from e