import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.models.models import Reporte, Medicion, Animal, Hato, Usuario
from app.schemas.schemas import ReporteCreate, ReporteResponse
from app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.post("/", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
def crear_reporte(
    datos: ReporteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Genera un reporte y lo guarda en la BD.
    Por ahora guarda los parámetros — la generación del archivo
    PDF/Excel se agrega después.
    """
    # Validar que el hato pertenece al usuario si se especificó
    if datos.hato_id:
        hato = db.query(Hato).filter(
            Hato.id == datos.hato_id,
            Hato.propietario_id == current_user.id
        ).first()
        if not hato:
            raise HTTPException(status_code=404, detail="Hato no encontrado")

    # Validar que el animal existe si se especificó
    if datos.animal_id:
        animal = db.query(Animal).join(Hato).filter(
            Animal.id == datos.animal_id,
            Hato.propietario_id == current_user.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal no encontrado")

    reporte = Reporte(
        titulo          = datos.titulo,
        tipo            = datos.tipo,
        formato         = datos.formato,
        hato_id         = datos.hato_id,
        animal_id       = datos.animal_id,
        generado_por_id = current_user.id,
        parametros      = {
            "fecha_desde": datos.fecha_desde.isoformat() if datos.fecha_desde else None,
            "fecha_hasta": datos.fecha_hasta.isoformat() if datos.fecha_hasta else None,
        },
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


@router.get("/", response_model=list[ReporteResponse])
def listar_reportes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista todos los reportes generados por el usuario."""
    return db.query(Reporte).filter(
        Reporte.generado_por_id == current_user.id
    ).order_by(Reporte.fecha_generado.desc()).all()


@router.get("/{reporte_id}", response_model=ReporteResponse)
def obtener_reporte(
    reporte_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Obtiene un reporte específico."""
    reporte = db.query(Reporte).filter(
        Reporte.id == reporte_id,
        Reporte.generado_por_id == current_user.id
    ).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return reporte


@router.delete("/{reporte_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_reporte(
    reporte_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina un reporte."""
    reporte = db.query(Reporte).filter(
        Reporte.id == reporte_id,
        Reporte.generado_por_id == current_user.id
    ).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    db.delete(reporte)
    db.commit()