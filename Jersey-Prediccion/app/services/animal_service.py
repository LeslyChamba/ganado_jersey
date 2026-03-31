# app/services/animal_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.animal import Animal
from app.schemas.animal import AnimalCreate, AnimalUpdate, AnimalWithHistory
from fastapi import HTTPException


async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> tuple[list[Animal], int]:
    count_q = select(func.count()).select_from(Animal)
    total = (await db.execute(count_q)).scalar_one()

    q = select(Animal).offset(skip).limit(limit).order_by(Animal.created_at.desc())
    result = await db.execute(q)
    animals = result.scalars().all()
    return list(animals), total


async def get_by_id(db: AsyncSession, animal_id: str) -> Animal:
    q = select(Animal).where(Animal.id == animal_id).options(selectinload(Animal.analyses))
    result = await db.execute(q)
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(status_code=404, detail=f"Animal {animal_id} no encontrado")
    return animal


async def get_by_arete(db: AsyncSession, arete: str) -> Animal | None:
    q = select(Animal).where(Animal.arete == arete.upper())
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: AnimalCreate) -> Animal:
    # Verificar que el arete no exista
    existing = await get_by_arete(db, data.arete)
    if existing:
        raise HTTPException(status_code=409, detail=f"El arete '{data.arete}' ya existe")

    animal = Animal(**data.model_dump())
    db.add(animal)
    await db.flush()
    await db.refresh(animal)
    return animal


async def update(db: AsyncSession, animal_id: str, data: AnimalUpdate) -> Animal:
    animal = await get_by_id(db, animal_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(animal, field, value)
    await db.flush()
    await db.refresh(animal)
    return animal


async def delete(db: AsyncSession, animal_id: str) -> None:
    animal = await get_by_id(db, animal_id)
    await db.delete(animal)


async def get_with_history(db: AsyncSession, animal_id: str) -> AnimalWithHistory:
    animal = await get_by_id(db, animal_id)
    analyses = animal.analyses

    last = analyses[-1] if analyses else None
    return AnimalWithHistory(
        **{c.key: getattr(animal, c.key) for c in Animal.__table__.columns},
        total_analyses=len(analyses),
        ultima_masa_kg=last.masa_estimada_kg if last else None,
        ultimo_bcs=last.bcs_score if last else None,
    )
