import logging
import os
from pathlib import Path

logger = logging.getLogger("jer-weight.models")


def descargar_modelos():
    """
    Descarga los modelos desde Hugging Face si no existen localmente.
    Si HF_TOKEN o HF_REPO_ID no están configurados, omite la descarga
    (útil para desarrollo local donde los modelos ya existen).
    """
    try:
        from huggingface_hub import hf_hub_download
        from app.core.config import settings
    except ImportError:
        logger.warning("⚠️  huggingface_hub no instalado — omitiendo descarga de modelos")
        return

    # Si no hay repo configurado, no intentar descargar
    if not settings.HF_REPO_ID or not settings.HF_TOKEN:
        logger.info("ℹ️  HF_REPO_ID/HF_TOKEN no configurados — usando modelos locales")
        return

    MODELOS = {
        "mass_model.pt":      settings.MASS_MODEL_PATH,
        "bcs_model.pt":       settings.BCS_MODEL_PATH,
        "sam_checkpoint.pth": settings.SAM_CHECKPOINT_PATH,
        "yolov8_bcs.pt":      settings.YOLO_BCS_PATH,
    }

    Path("models_pt").mkdir(exist_ok=True)

    for filename, local_path in MODELOS.items():
        if os.path.exists(local_path):
            logger.info(f"✅ Modelo ya existe: {local_path}")
            continue

        logger.info(f"⬇️  Descargando {filename} desde Hugging Face...")
        try:
            hf_hub_download(
                repo_id=settings.HF_REPO_ID,
                filename=filename,
                local_dir="models_pt/",
                token=settings.HF_TOKEN or None,
            )
            logger.info(f"✅ {filename} descargado correctamente")
        except Exception as e:
            logger.error(f"❌ Error descargando {filename}: {e}")
            raise RuntimeError(f"No se pudo descargar {filename}") from e