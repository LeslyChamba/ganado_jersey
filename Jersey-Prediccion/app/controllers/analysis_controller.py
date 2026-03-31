# app/controllers/analysis_controller.py
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import get_db
from app.services import analysis_service
from app.views.response import success, created

router = APIRouter(prefix="/analysis", tags=["Análisis"])


@router.post("/")
async def analyze_image(
    animal_id: str = Form(..., description="UUID del animal en el sistema"),
    bcs: float = Form(..., ge=1.0, le=5.0, description="BCS evaluado visualmente (1–5)"),
    file: UploadFile = File(..., description="Foto lateral del bovino con barra de referencia"),
    db: AsyncSession = Depends(get_db),
):
    """
    Pipeline completo de análisis:
    1. Recibe imagen + animal_id + BCS del usuario
    2. OpenCV extrae lc, pt, altura, features
    3. XGBoost predice masa corporal
    4. Guarda en PostgreSQL
    5. Retorna resultado estructurado
    """
    result = await analysis_service.run_analysis(db, file, animal_id, bcs=bcs)
    return created(result, "Análisis completado")


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str, db: AsyncSession = Depends(get_db)):
    result = await analysis_service.get_by_id(db, analysis_id)
    return success(result, "Análisis encontrado")
