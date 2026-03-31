# app/controllers/animal_controller.py
"""
CONTROLADOR DE ANIMALES
Orquesta: request → service → view (respuesta JSON)
No contiene lógica de negocio — solo coordina.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from app.services import animal_service
from app.schemas.animal import AnimalCreate, AnimalUpdate
from app.views.response import success, created, not_found, paginated

router = APIRouter(prefix="/animals", tags=["Animales"])


@router.get("/")
async def list_animals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos los animales registrados (paginado)."""
    animals, total = await animal_service.get_all(db, skip=skip, limit=limit)
    data = [a.__dict__ for a in animals]
    return paginated(data, total=total, page=skip // limit + 1, page_size=limit)


@router.get("/{animal_id}")
async def get_animal(animal_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna un animal con su historial resumido."""
    animal = await animal_service.get_with_history(db, animal_id)
    return success(animal, "Animal encontrado")


@router.post("/")
async def create_animal(data: AnimalCreate, db: AsyncSession = Depends(get_db)):
    """Registra un nuevo animal en el sistema."""
    animal = await animal_service.create(db, data)
    return created(animal.__dict__, f"Animal {animal.arete} registrado")


@router.put("/{animal_id}")
async def update_animal(
    animal_id: str,
    data: AnimalUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza datos de un animal existente."""
    animal = await animal_service.update(db, animal_id, data)
    return success(animal.__dict__, "Animal actualizado")


@router.delete("/{animal_id}")
async def delete_animal(animal_id: str, db: AsyncSession = Depends(get_db)):
    """Elimina un animal y todos sus análisis."""
    await animal_service.delete(db, animal_id)
    return success(None, "Animal eliminado")


@router.get("/{animal_id}/evolution")
async def get_evolution(animal_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna la evolución temporal de masa y BCS de un animal."""
    from app.services import analysis_service
    evo = await analysis_service.get_evolution(db, animal_id)
    return success(evo, "Evolución cargada")
