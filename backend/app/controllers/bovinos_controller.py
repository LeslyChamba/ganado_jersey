from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional

from app.db.database import get_db
from app.models.models import Animal, Hato, Usuario, Medicion
from app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/admin/bovinos", tags=["Admin - Bovinos"])


def _ultima_medicion_subquery(db: Session):
    """Subconsulta que trae solo la medición más reciente por animal."""
    return (
        db.query(
            Medicion.animal_id,
            func.max(Medicion.fecha_medicion).label("ultima_fecha"),
        )
        .group_by(Medicion.animal_id)
        .subquery()
    )


@router.get("")
def listar_todos_bovinos(
    peso_min: Optional[float] = Query(None),
    peso_max: Optional[float] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sub = _ultima_medicion_subquery(db)

    # Join Animal → Hato → propietario → última medición
    rows = (
        db.query(Animal, Hato, Usuario, Medicion)
        .join(Hato,    Animal.hato_id       == Hato.id)
        .join(Usuario, Hato.propietario_id  == Usuario.id)
        .outerjoin(sub,     Animal.id == sub.c.animal_id)
        .outerjoin(
            Medicion,
            (Medicion.animal_id     == Animal.id) &
            (Medicion.fecha_medicion == sub.c.ultima_fecha)
        )
        .order_by(desc(sub.c.ultima_fecha).nullslast())
        .all()
    )

    # Aplicar filtros de peso en Python (sobre la medición ya traída)
    resultado = []
    for animal, hato, usuario, medicion in rows:
        peso = medicion.peso_estimado_kg if medicion else None

        if peso_min is not None and (peso is None or peso < peso_min):
            continue
        if peso_max is not None and (peso is None or peso > peso_max):
            continue

        resultado.append({
            "id":              str(animal.id),
            "arete":           animal.arete,
            "nombre":          animal.nombre,
            "raza":            animal.raza,
            "ultimo_peso_kg":  round(peso, 1)         if peso               else None,
            "ultimo_bcs":      round(medicion.bcs, 2) if medicion           else None,
            "ultima_medicion": medicion.fecha_medicion.isoformat() if medicion else None,
            "hato_nombre":     hato.nombre,
            "finca":           hato.finca,
            "ganadero":        f"{usuario.nombre} {usuario.apellido}",
            "ganadero_email":  usuario.email,
        })

    return resultado


@router.get("/stats")
def stats_bovinos(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total = db.query(func.count(Animal.id)).scalar() or 0

    # Stats desde la tabla Medicion (última por animal)
    sub = _ultima_medicion_subquery(db)

    ultimas = (
        db.query(Medicion)
        .join(sub,
            (Medicion.animal_id      == sub.c.animal_id) &
            (Medicion.fecha_medicion == sub.c.ultima_fecha)
        )
        .all()
    )

    pesos = [m.peso_estimado_kg for m in ultimas if m.peso_estimado_kg]
    bcs_vals = [m.bcs for m in ultimas if m.bcs]
    en_alerta = sum(1 for m in ultimas if m.bcs and m.bcs < 2.5)

    return {
        "total":         total,
        "con_medicion":  len(ultimas),
        "peso_promedio": round(sum(pesos) / len(pesos), 1) if pesos    else None,
        "bcs_promedio":  round(sum(bcs_vals) / len(bcs_vals), 2) if bcs_vals else None,
        "en_alerta":     en_alerta,
        "peso_max":      round(max(pesos), 1) if pesos else None,
        "peso_min":      round(min(pesos), 1) if pesos else None,
    }