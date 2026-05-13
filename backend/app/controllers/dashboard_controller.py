import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from app.core.encryption import decrypt
from app.controllers.auth_controller import get_current_user, require_admin
from app.db.database import get_db
from app.models.models import (
    AccionAuditoria, Animal, AuditoriaLog,
    Hato, Medicion, RolUsuario, Usuario,
)
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["Dashboard y Auditoría"])


# ════════════════════════════════════════════════════════
#  SCHEMAS DE RESPUESTA
# ════════════════════════════════════════════════════════

class AuditoriaLogResponse(BaseModel):
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID]
    usuario_email: Optional[str]
    accion: AccionAuditoria
    tabla_afectada: Optional[str]
    registro_id: Optional[str]
    datos_antes: Optional[dict]
    datos_despues: Optional[dict]
    ip_address: Optional[str]
    detalle: Optional[str]
    fecha: datetime

    model_config = {"from_attributes": True}


class DashboardAdminResponse(BaseModel):
    total_usuarios: int
    usuarios_activos: int
    total_ganaderos: int
    total_bovinos: int
    total_evaluaciones: int
    evaluaciones_hoy: int
    animales_en_alerta: int


class AnimalAlertaItem(BaseModel):
    animal_id: uuid.UUID
    arete: str
    nombre: Optional[str]
    hato_nombre: str
    ultimo_bcs: Optional[float]
    ultimo_peso_kg: Optional[float]
    motivo: str


class DashboardGanaderoResponse(BaseModel):
    total_animales: int
    evaluaciones_hoy: int
    animales_en_alerta: int
    bcs_promedio: Optional[float]
    peso_promedio_kg: Optional[float]
    total_hatos: int


# ════════════════════════════════════════════════════════
#  HU-02 — LOG DE AUDITORÍA (solo Admin)
# ════════════════════════════════════════════════════════

@router.get("/auditoria", response_model=list[AuditoriaLogResponse])
def listar_logs_auditoria(
    usuario_email: Optional[str] = Query(None, description="Filtrar por email de usuario"),
    accion: Optional[AccionAuditoria] = Query(None, description="Tipo de acción"),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    tabla: Optional[str] = Query(None, description="Tabla afectada"),
    limite: int = Query(100, le=500, description="Máximo registros a retornar"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
    """
    HU-02: Lista logs de auditoría.
    Solo accesible por Administrador. No editable ni eliminable.
    Filtros: usuario, fecha, tipo de acción.
    """
    q = db.query(AuditoriaLog)

    if usuario_email:
        q = q.filter(AuditoriaLog.usuario_email.ilike(f"%{usuario_email}%"))
    if accion:
        q = q.filter(AuditoriaLog.accion == accion)
    if fecha_desde:
        q = q.filter(AuditoriaLog.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(AuditoriaLog.fecha <= fecha_hasta)
    if tabla:
        q = q.filter(AuditoriaLog.tabla_afectada == tabla)

    logs = q.order_by(AuditoriaLog.fecha.desc()).offset(offset).limit(limite).all()
    
    
    logs_formateados = []
    for log in logs:
        # Hacemos una copia de los datos del log
        log_dict = AuditoriaLogResponse.model_validate(log).model_dump()
        
        # Intentamos desencriptar el correo
        if log_dict.get("usuario_email"):
            try:
                log_dict["usuario_email"] = decrypt(log_dict["usuario_email"])
            except Exception:
                # Si falla (ej. era un log antiguo guardado en texto plano como el "login"), 
                # lo dejamos como estaba.
                pass 
                
        logs_formateados.append(log_dict)

    return logs_formateados
    
    return [AuditoriaLogResponse.model_validate(log) for log in logs]


# ════════════════════════════════════════════════════════
#  HU-03 — DASHBOARD ADMINISTRATIVO
# ════════════════════════════════════════════════════════

@router.get("/admin", response_model=DashboardAdminResponse)
def dashboard_admin(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
    """
    HU-03: Dashboard administrativo.
    Muestra totales de usuarios, bovinos y evaluaciones.
    Se actualiza automáticamente con cada consulta.
    """
    hoy_inicio = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_usuarios = db.query(func.count(Usuario.id)).scalar() or 0
    usuarios_activos = db.query(func.count(Usuario.id)).filter(Usuario.activo == True).scalar() or 0
    total_ganaderos = db.query(func.count(Usuario.id)).filter(
        Usuario.rol == RolUsuario.GANADERO
    ).scalar() or 0

    total_bovinos = db.query(func.count(Animal.id)).scalar() or 0
    total_evaluaciones = db.query(func.count(Medicion.id)).scalar() or 0

    evaluaciones_hoy = db.query(func.count(Medicion.id)).filter(
        Medicion.fecha_medicion >= hoy_inicio
    ).scalar() or 0

    animales_en_alerta = _contar_animales_en_alerta(db)

    return DashboardAdminResponse(
        total_usuarios=total_usuarios,
        usuarios_activos=usuarios_activos,
        total_ganaderos=total_ganaderos,
        total_bovinos=total_bovinos,
        total_evaluaciones=total_evaluaciones,
        evaluaciones_hoy=evaluaciones_hoy,
        animales_en_alerta=animales_en_alerta,
    )


# ════════════════════════════════════════════════════════
#  HU-11 — DASHBOARD GANADERO
# ════════════════════════════════════════════════════════

@router.get("/ganadero", response_model=DashboardGanaderoResponse)
def dashboard_ganadero(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    HU-11: Dashboard del ganadero.
    Muestra: total animales, evaluaciones del día, animales en alerta,
    promedios de BCS y masa, total de hatos.
    Se actualiza tras cada estimación.
    """
    hoy_inicio = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Hatos del ganadero
    hato_ids = [
        h.id for h in db.query(Hato.id).filter(
            Hato.propietario_id == current_user.id, Hato.activo == True
        ).all()
    ]
    total_hatos = len(hato_ids)

    if not hato_ids:
        return DashboardGanaderoResponse(
            total_animales=0, evaluaciones_hoy=0, animales_en_alerta=0,
            bcs_promedio=None, peso_promedio_kg=None, total_hatos=0
        )

    # Animales del ganadero
    animal_ids = [
        a.id for a in db.query(Animal.id).filter(Animal.hato_id.in_(hato_ids)).all()
    ]
    total_animales = len(animal_ids)

    # Evaluaciones de hoy
    evaluaciones_hoy = db.query(func.count(Medicion.id)).filter(
        Medicion.animal_id.in_(animal_ids),
        Medicion.fecha_medicion >= hoy_inicio
    ).scalar() or 0

    # Promedios (última medición de cada animal)
    stats = db.query(
        func.avg(Medicion.bcs).label("bcs_prom"),
        func.avg(Medicion.peso_estimado_kg).label("peso_prom"),
    ).filter(Medicion.animal_id.in_(animal_ids)).first()

    animales_en_alerta = _contar_animales_en_alerta_ganadero(db, animal_ids)

    return DashboardGanaderoResponse(
        total_animales=total_animales,
        evaluaciones_hoy=evaluaciones_hoy,
        animales_en_alerta=animales_en_alerta,
        bcs_promedio=round(stats.bcs_prom, 2) if stats.bcs_prom else None,
        peso_promedio_kg=round(stats.peso_prom, 1) if stats.peso_prom else None,
        total_hatos=total_hatos,
    )


# ════════════════════════════════════════════════════════
#  HU-13 — ANIMALES EN ALERTA (con detalle)
# ════════════════════════════════════════════════════════

@router.get("/alertas", response_model=list[AnimalAlertaItem])
def animales_en_alerta(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    HU-13: Lista de animales en alerta (BCS < 2.5).
    Al hacer clic en el contador del dashboard se muestra esta lista.
    Se actualiza automáticamente tras cada estimación.
    """
    hato_ids = [
        h.id for h in db.query(Hato.id).filter(
            Hato.propietario_id == current_user.id, Hato.activo == True
        ).all()
    ]
    if not hato_ids:
        return []

    animal_ids = [
        a.id for a in db.query(Animal.id).filter(Animal.hato_id.in_(hato_ids)).all()
    ]
    if not animal_ids:
        return []

    # Subconsulta: última medición de cada animal
    ultima_med_sub = (
        db.query(
            Medicion.animal_id,
            func.max(Medicion.fecha_medicion).label("ultima_fecha")
        )
        .filter(Medicion.animal_id.in_(animal_ids))
        .group_by(Medicion.animal_id)
        .subquery()
    )

    # Join para obtener la medición más reciente de cada animal
    ultimas = (
        db.query(Medicion)
        .join(
            ultima_med_sub,
            and_(
                Medicion.animal_id == ultima_med_sub.c.animal_id,
                Medicion.fecha_medicion == ultima_med_sub.c.ultima_fecha
            )
        )
        .filter(Medicion.bcs < 2.5)
        .all()
    )

    # Pesos normales Jersey hembra: 280 – 500 kg (RF-14)
    PESO_MIN_NORMAL = 280.0
    PESO_MAX_NORMAL = 500.0

    resultado = []
    for med in ultimas:
        animal = db.query(Animal).filter(Animal.id == med.animal_id).first()
        if not animal:
            continue
        hato = db.query(Hato).filter(Hato.id == animal.hato_id).first()

        motivos = []
        if med.bcs is not None and med.bcs < 2.5:
            motivos.append(f"BCS {med.bcs:.2f} — por debajo del mínimo (2.5)")
        if med.peso_estimado_kg is not None:
            if med.peso_estimado_kg < PESO_MIN_NORMAL:
                motivos.append(f"Peso {med.peso_estimado_kg:.0f} kg — por debajo del rango Jersey ({PESO_MIN_NORMAL:.0f} kg)")
            elif med.peso_estimado_kg > PESO_MAX_NORMAL:
                motivos.append(f"Peso {med.peso_estimado_kg:.0f} kg — por encima del rango Jersey ({PESO_MAX_NORMAL:.0f} kg)")

        if motivos:
            resultado.append(AnimalAlertaItem(
                animal_id=animal.id,
                arete=animal.arete,
                nombre=animal.nombre,
                hato_nombre=hato.nombre if hato else "Sin hato",
                ultimo_bcs=med.bcs,
                ultimo_peso_kg=med.peso_estimado_kg,
                motivo=" | ".join(motivos),
            ))

    return resultado


# ════════════════════════════════════════════════════════
#  HELPERS INTERNOS
# ════════════════════════════════════════════════════════

def _contar_animales_en_alerta(db: Session) -> int:
    """Cuenta animales con BCS < 2.5 en su última medición (todos los hatos)."""
    ultima_med_sub = (
        db.query(
            Medicion.animal_id,
            func.max(Medicion.fecha_medicion).label("ultima_fecha")
        )
        .group_by(Medicion.animal_id)
        .subquery()
    )
    return db.query(func.count(Medicion.id)).join(
        ultima_med_sub,
        and_(
            Medicion.animal_id == ultima_med_sub.c.animal_id,
            Medicion.fecha_medicion == ultima_med_sub.c.ultima_fecha
        )
    ).filter(Medicion.bcs < 2.5).scalar() or 0


def _contar_animales_en_alerta_ganadero(db: Session, animal_ids: list) -> int:
    """Cuenta alertas (BCS < 2.5 O peso fuera de rango Jersey) del ganadero."""
    if not animal_ids:
        return 0
    from sqlalchemy import or_
    ultima_med_sub = (
        db.query(
            Medicion.animal_id,
            func.max(Medicion.fecha_medicion).label("ultima_fecha")
        )
        .filter(Medicion.animal_id.in_(animal_ids))
        .group_by(Medicion.animal_id)
        .subquery()
    )
    return db.query(func.count(Medicion.id)).join(
        ultima_med_sub,
        and_(
            Medicion.animal_id == ultima_med_sub.c.animal_id,
            Medicion.fecha_medicion == ultima_med_sub.c.ultima_fecha
        )
    ).filter(
        or_(
            Medicion.bcs < 2.5,
            Medicion.peso_estimado_kg < 280.0,
            Medicion.peso_estimado_kg > 500.0,
        )
    ).scalar() or 0