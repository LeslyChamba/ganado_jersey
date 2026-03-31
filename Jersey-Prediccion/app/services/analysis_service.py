# app/services/analysis_service.py
import hashlib
import uuid
import aiofiles
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, UploadFile

from app.models.analysis import Analysis
from app.models.animal import Animal
from app.services import inference_service
from app.services.vision.morphometry import save_debug_image
from app.schemas.analysis import AnalysisOut, EvolutionOut, EvolutionPoint
from config.settings import get_settings

settings = get_settings()
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = Path("uploads/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ── Validación de imagen ──────────────────────────────────────────────────────

async def validate_and_read_image(file: UploadFile) -> bytes:
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Formato no permitido: .{ext}. Use: {settings.ALLOWED_EXTENSIONS}",
        )
    content = await file.read()
    max_bytes = settings.IMAGE_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Imagen muy grande. Máximo {settings.IMAGE_MAX_SIZE_MB} MB",
        )
    return content


# ── Guardar imagen en disco ───────────────────────────────────────────────────

async def save_image(content: bytes, animal_arete: str) -> tuple[str, str]:
    sha256 = hashlib.sha256(content).hexdigest()
    filename = f"{animal_arete}_{uuid.uuid4().hex[:8]}.jpg"
    filepath = UPLOAD_DIR / filename
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)
    return str(filepath), sha256


# ── Análisis principal ────────────────────────────────────────────────────────

async def run_analysis(
    db: AsyncSession,
    file: UploadFile,
    animal_id: str,
    bcs: float = 3.0,          # ← BCS ingresado por el usuario en el formulario
) -> AnalysisOut:
    """
    Pipeline completo:
      1. Valida imagen
      2. Verifica animal en BD
      3. OpenCV → extrae lc, pt, features
      4. XGBoost → predice peso
      5. Guarda en PostgreSQL
      6. Retorna AnalysisOut
    """
    # 1. Leer imagen
    image_bytes = await validate_and_read_image(file)

    # 2. Animal
    result = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")

    # 3 + 4. OpenCV + XGBoost
    pred = await inference_service.predict(image_bytes, bcs=bcs)

    # Guardar imagen de debug con anotaciones
    debug_path = str(DEBUG_DIR / f"{animal.arete}_{uuid.uuid4().hex[:6]}_debug.jpg")
    from app.services.vision.morphometry import process_image as _proc
    morph_raw = _proc(image_bytes, settings.SCALE_COLOR, settings.REFERENCE_CM)
    save_debug_image(morph_raw, debug_path)

    # 5. Guardar imagen original
    img_path, img_hash = await save_image(image_bytes, animal.arete)

    # 6. Persistir análisis en PostgreSQL
    analysis = Analysis(
        animal_id=animal_id,
        masa_estimada_kg=pred.masa_kg,
        masa_margen_error_kg=pred.masa_margen_error_kg,
        masa_confianza=pred.masa_confianza,
        bcs_score=pred.bcs_score,
        bcs_confianza=pred.bcs_confianza,
        largo_corporal_cm=pred.morfometria.get("largo_corporal_cm"),
        altura_cruz_cm=pred.morfometria.get("altura_cruz_cm"),
        perimetro_toracico_cm=pred.morfometria.get("perimetro_toracico_cm"),
        ancho_cadera_cm=pred.morfometria.get("ancho_cadera_cm"),
        imagen_path=img_path,
        imagen_hash=img_hash,
        metadata_json={
            "scale_found": pred.scale_found,
            "vision_confidence": pred.vision_confidence,
            "debug_image_path": debug_path,
            "bcs_source": "user_input",
        },
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)

    return AnalysisOut.from_orm_flat(analysis)


# ── Consultas ─────────────────────────────────────────────────────────────────

async def get_by_id(db: AsyncSession, analysis_id: str) -> AnalysisOut:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return AnalysisOut.from_orm_flat(obj)


async def get_evolution(db: AsyncSession, animal_id: str) -> EvolutionOut:
    result_animal = await db.execute(select(Animal).where(Animal.id == animal_id))
    animal = result_animal.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")

    result = await db.execute(
        select(Analysis)
        .where(Analysis.animal_id == animal_id)
        .order_by(Analysis.created_at.asc())
    )
    analyses = result.scalars().all()
    puntos = [
        EvolutionPoint(fecha=a.created_at, masa_kg=a.masa_estimada_kg, bcs_score=a.bcs_score)
        for a in analyses
    ]
    return EvolutionOut(animal_id=animal_id, arete=animal.arete, puntos=puntos)
