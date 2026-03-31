# app/schemas/analysis.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ── Morfometría ──
class MorphometricsOut(BaseModel):
    largo_corporal_cm: Optional[float] = None
    altura_cruz_cm: Optional[float] = None
    perimetro_toracico_cm: Optional[float] = None
    ancho_cadera_cm: Optional[float] = None


# ── Resultado masa ──
class MasaOut(BaseModel):
    estimada_kg: float
    margen_error_kg: Optional[float] = None
    confianza: Optional[float] = Field(None, ge=0.0, le=1.0)


# ── Resultado BCS ──
class BCSOut(BaseModel):
    score: float = Field(..., ge=1.0, le=5.0)
    confianza: Optional[float] = Field(None, ge=0.0, le=1.0)
    descripcion: Optional[str] = None


# ── Salida completa de un análisis ──
class AnalysisOut(BaseModel):
    id: str
    animal_id: str
    masa: MasaOut
    bcs: BCSOut
    morfometria: MorphometricsOut
    imagen_path: Optional[str] = None
    metadata_json: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_flat(cls, obj) -> "AnalysisOut":
        """Convierte el modelo ORM (campos planos) al schema anidado."""
        return cls(
            id=obj.id,
            animal_id=obj.animal_id,
            masa=MasaOut(
                estimada_kg=obj.masa_estimada_kg,
                margen_error_kg=obj.masa_margen_error_kg,
                confianza=obj.masa_confianza,
            ),
            bcs=BCSOut(
                score=obj.bcs_score,
                confianza=obj.bcs_confianza,
                descripcion=_bcs_descripcion(obj.bcs_score),
            ),
            morfometria=MorphometricsOut(
                largo_corporal_cm=obj.largo_corporal_cm,
                altura_cruz_cm=obj.altura_cruz_cm,
                perimetro_toracico_cm=obj.perimetro_toracico_cm,
                ancho_cadera_cm=obj.ancho_cadera_cm,
            ),
            imagen_path=obj.imagen_path,
            metadata_json=obj.metadata_json,
            created_at=obj.created_at,
        )


# ── Evolución temporal ──
class EvolutionPoint(BaseModel):
    fecha: datetime
    masa_kg: float
    bcs_score: float

    model_config = {"from_attributes": True}


class EvolutionOut(BaseModel):
    animal_id: str
    arete: str
    puntos: list[EvolutionPoint]


def _bcs_descripcion(score: float) -> str:
    s = round(score)
    return {
        1: "Caquéctico — reservas agotadas, atención urgente",
        2: "Delgado — falta cobertura muscular y grasa",
        3: "Moderado — condición aceptable, monitorear",
        4: "Bueno — excelente estado, nivel óptimo",
        5: "Obeso — exceso de grasa, riesgo metabólico",
    }.get(s, "Sin clasificación")
