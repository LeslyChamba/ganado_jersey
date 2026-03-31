# app/schemas/animal.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class SexoEnum(str, Enum):
    macho = "macho"
    hembra = "hembra"
    castrado = "castrado"


# ── Entrada: crear animal ──
class AnimalCreate(BaseModel):
    arete: str = Field(..., min_length=1, max_length=50, examples=["BOV-001"])
    notas: Optional[str] = Field(None, max_length=500)

    @field_validator("arete")
    @classmethod
    def arete_uppercase(cls, v: str) -> str:
        return v.strip().upper()



# ── Salida: animal simple ──
class AnimalOut(BaseModel):
    id: str
    arete: str
    notas: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Salida: animal con historial completo ──
class AnimalWithHistory(AnimalOut):
    total_analyses: int = 0
    ultima_masa_kg: Optional[float] = None
    ultimo_bcs: Optional[float] = None
