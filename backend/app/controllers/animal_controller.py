import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.exceptions import registrar_error_auditoria  
from fastapi import Request
from app.db.database import get_db
from app.models.models import Animal, Hato, Medicion, Usuario
from app.schemas.schemas import (
    AnimalCreate, AnimalUpdate, AnimalResponse,
    HatoCreate, HatoUpdate, HatoResponse,
    EstadisticasHato
)
from app.controllers.auth_controller import get_current_user
from app.services.auditoria_service import registrar_log
from app.models.models import AccionAuditoria
# ════════════════════════════════════════════════════════
#  ROUTER DE HATOS
# ════════════════════════════════════════════════════════

hato_router = APIRouter(prefix="/hatos", tags=["Hatos"])


@hato_router.post("/", response_model=HatoResponse, status_code=status.HTTP_201_CREATED)
def crear_hato(
    datos: HatoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    hato = Hato(**datos.model_dump(), propietario_id=current_user.id)
    db.add(hato)
    db.commit()
    db.refresh(hato)
    r = HatoResponse.model_validate(hato)
    r.total_animales = db.query(func.count(Animal.id)).filter(
        Animal.hato_id == hato.id
    ).scalar()
    return r


@hato_router.get("/", response_model=list[HatoResponse])
def listar_hatos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    hatos = db.query(Hato).filter(
        Hato.propietario_id == current_user.id,
        Hato.activo == True
    ).all()
    result = []
    for hato in hatos:
        r = HatoResponse.model_validate(hato)
        r.total_animales = db.query(func.count(Animal.id)).filter(
            Animal.hato_id == hato.id
        ).scalar()
        result.append(r)
    return result


@hato_router.get("/{hato_id}", response_model=HatoResponse)
def obtener_hato(
    hato_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    hato = _get_hato_o_404(hato_id, current_user.id, db)
    r = HatoResponse.model_validate(hato)
    r.total_animales = db.query(func.count(Animal.id)).filter(
        Animal.hato_id == hato.id
    ).scalar()
    return r


@hato_router.put("/{hato_id}", response_model=HatoResponse)
def actualizar_hato(
    hato_id: uuid.UUID,
    datos: HatoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    hato = _get_hato_o_404(hato_id, current_user.id, db)
    for campo, valor in datos.model_dump(exclude_none=True).items():
        setattr(hato, campo, valor)
    db.commit()
    db.refresh(hato)
    return HatoResponse.model_validate(hato)


@hato_router.delete("/{hato_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_hato(
    hato_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    hato = _get_hato_o_404(hato_id, current_user.id, db)
    hato.activo = False
    db.commit()


@hato_router.get("/{hato_id}/estadisticas", response_model=EstadisticasHato)
def estadisticas_hato(
    hato_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    _get_hato_o_404(hato_id, current_user.id, db)

    animal_ids = [a.id for a in db.query(Animal.id).filter(
        Animal.hato_id == hato_id
    ).all()]

    total_animales = len(animal_ids)

    stats = db.query(
        func.avg(Medicion.peso_estimado_kg).label("peso_promedio"),
        func.avg(Medicion.bcs).label("bcs_promedio"),
        func.count(Medicion.id).label("total_mediciones"),
        func.max(Medicion.fecha_medicion).label("ultima_medicion"),
    ).filter(Medicion.animal_id.in_(animal_ids)).first()

    bajo_bcs = db.query(func.count(Medicion.id)).filter(
        Medicion.animal_id.in_(animal_ids), Medicion.bcs < 2.5
    ).scalar()

    sobre_bcs = db.query(func.count(Medicion.id)).filter(
        Medicion.animal_id.in_(animal_ids), Medicion.bcs > 4.0
    ).scalar()

    return EstadisticasHato(
        total_animales=total_animales,
        peso_promedio_kg=round(stats.peso_promedio, 1) if stats.peso_promedio else None,
        bcs_promedio=round(stats.bcs_promedio, 2) if stats.bcs_promedio else None,
        total_mediciones=stats.total_mediciones or 0,
        ultima_medicion=stats.ultima_medicion,
        animales_bajo_bcs=bajo_bcs or 0,
        animales_sobre_bcs=sobre_bcs or 0,
    )


def _get_hato_o_404(hato_id: uuid.UUID, usuario_id: uuid.UUID, db: Session) -> Hato:
    hato = db.query(Hato).filter(
        Hato.id == hato_id,
        Hato.propietario_id == usuario_id,
        Hato.activo == True
    ).first()
    if not hato:
        raise HTTPException(status_code=404, detail="Hato no encontrado")
    return hato


# ════════════════════════════════════════════════════════
#  ROUTER DE ANIMALES
# ════════════════════════════════════════════════════════

animal_router = APIRouter(prefix="/animales", tags=["Animales"])


@animal_router.post("/", response_model=AnimalResponse, status_code=status.HTTP_201_CREATED)
def crear_animal(
    datos: AnimalCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    try:
        hato = db.query(Hato).filter(
            Hato.id == datos.hato_id,
            Hato.propietario_id == current_user.id
        ).first()
        if not hato:
            raise HTTPException(status_code=404, detail="Hato no encontrado")

        existente = db.query(Animal).filter(
            Animal.hato_id == datos.hato_id,
            Animal.arete == datos.arete
        ).first()
        if existente:
            raise ValueError(f"Intento de duplicar arete: {datos.arete}")

        animal = Animal(**datos.model_dump())
        db.add(animal)
        db.commit()
        db.refresh(animal)

        datos_para_log = datos.model_dump(mode="json")

        # LOG DE ÉXITO 
        registrar_log(
            db=db,
            accion=AccionAuditoria.CREAR,
            usuario_id=current_user.id,
            usuario_email=current_user.email,
            tabla="animales",
            registro_id=str(animal.id),
            despues=datos.model_dump(),
            ip=request.client.host
        )
        
        return _enriquecer_animal(animal, db)

    except Exception as e:
        db.rollback()
        
        # 4. LOG DE ERROR 
        # Esto demuestra el fallo aunque la vaca no se cree
        id_recurso_str = str(datos.arete) if datos.arete else "Desconocido" 
        registrar_error_auditoria(
            db=db,
            usuario_email=current_user.email,
            modulo="Animales",
            accion="Crear Animal",
            error=e,
            id_recurso=id_recurso_str # Guardamos el ARETE que dio problemas
        )
        
        # Si era una validación nuestra, mandamos 400, si no 500
        detail = str(e) if isinstance(e, ValueError) else "Error interno del servidor"
        raise HTTPException(status_code=400, detail=detail)


@animal_router.get("/", response_model=list[AnimalResponse])
def listar_animales(
    hato_id: Optional[uuid.UUID] = Query(None),
    buscar: Optional[str] = Query(None, description="Buscar por arete o nombre"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    query = db.query(Animal).join(Hato).filter(
        Hato.propietario_id == current_user.id
    )
    if hato_id:
        query = query.filter(Animal.hato_id == hato_id)
    if buscar:
        query = query.filter(
            (Animal.arete.ilike(f"%{buscar}%")) | (Animal.nombre.ilike(f"%{buscar}%"))
        )
    return [_enriquecer_animal(a, db) for a in query.order_by(Animal.created_at.desc()).all()]


# ── NUEVO: buscar por arete exacto ──────────────────────────────────────────
@animal_router.get("/buscar/arete", response_model=Optional[AnimalResponse])
def buscar_por_arete(
    arete: str = Query(..., description="Arete exacto de la vaca"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Busca una vaca por arete exacto.
    Retorna la vaca si existe, o null si no existe.
    No lanza 404 — el frontend decide qué hacer.
    """
    animal = db.query(Animal).join(Hato).filter(
        Animal.arete == arete,
        Hato.propietario_id == current_user.id
    ).first()
    if not animal:
        return None
    return _enriquecer_animal(animal, db)


@animal_router.get("/{animal_id}", response_model=AnimalResponse)
def obtener_animal(
    animal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    return _enriquecer_animal(_get_animal_o_404(animal_id, current_user.id, db), db)


@animal_router.put("/{animal_id}", response_model=AnimalResponse)
def actualizar_animal(
    animal_id: uuid.UUID,
    datos: AnimalUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    animal = _get_animal_o_404(animal_id, current_user.id, db)
    for campo, valor in datos.model_dump(exclude_none=True).items():
        setattr(animal, campo, valor)
    db.commit()
    db.refresh(animal)
    return _enriquecer_animal(animal, db)


@animal_router.delete("/{animal_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_animal(
    animal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    animal = _get_animal_o_404(animal_id, current_user.id, db)
    db.delete(animal)
    db.commit()


@animal_router.get("/{animal_id}/mediciones")
def historial_mediciones(
    animal_id: uuid.UUID,
    limite: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    from app.schemas.schemas import MedicionResponse
    _get_animal_o_404(animal_id, current_user.id, db)
    mediciones = db.query(Medicion).filter(
        Medicion.animal_id == animal_id
    ).order_by(Medicion.fecha_medicion.desc()).limit(limite).all()
    return [MedicionResponse.model_validate(m) for m in mediciones]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _get_animal_o_404(animal_id: uuid.UUID, usuario_id: uuid.UUID, db: Session) -> Animal:
    animal = db.query(Animal).join(Hato).filter(
        Animal.id == animal_id,
        Hato.propietario_id == usuario_id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal no encontrado")
    return animal


def _enriquecer_animal(animal: Animal, db: Session) -> AnimalResponse:
    total = db.query(func.count(Medicion.id)).filter(
        Medicion.animal_id == animal.id
    ).scalar()
    ultima = db.query(Medicion).filter(
        Medicion.animal_id == animal.id
    ).order_by(Medicion.fecha_medicion.desc()).first()

    r = AnimalResponse.model_validate(animal)
    r.total_mediciones = total or 0
    if ultima:
        r.ultima_medicion = ultima.fecha_medicion
        r.ultimo_peso_kg  = ultima.peso_estimado_kg
        r.ultimo_bcs      = ultima.bcs
    return r



# Al CREAR un animal
def crear_animal(animal_data, db, usuario_actual, request):
    nuevo_animal = Animal(**animal_data.dict())
    db.add(nuevo_animal)
    db.commit()

    registrar_log(
        db=db,
        accion=AccionAuditoria.CREAR,
        usuario_id=usuario_actual.id,
        usuario_email=usuario_actual.email,
        tabla="animales",
        registro_id=nuevo_animal.id,
        despues=animal_data.dict(),
        ip=request.client.host
    )
    return nuevo_animal

# Al MODIFICAR un animal
def actualizar_animal(animal_id, animal_data, db, usuario_actual, request):
    animal = db.query(Animal).filter(Animal.id == animal_id).first()
    datos_antes = {"arete": animal.arete, "nombre": animal.nombre}  # guardas lo viejo

    for key, value in animal_data.dict().items():
        setattr(animal, key, value)
    db.commit()

    registrar_log(
        db=db,
        accion=AccionAuditoria.MODIFICAR,
        usuario_id=usuario_actual.id,
        usuario_email=usuario_actual.email,
        tabla="animales",
        registro_id=animal_id,
        antes=datos_antes,
        despues=animal_data.dict(),
        ip=request.client.host
    )
    return animal