import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_, or_          # ← or_ IMPORTADO AQUÍ, no lazy
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

# ── Criterios de alerta unificados (RF-14 Jersey) ─────────────────────────────
# CRÍTICO: usar ESTAS constantes en los 4 lugares donde se evalúa alerta.
# Cambiar aquí afecta contadores Y modal automáticamente.
BCS_ALERTA        = 2.5
PESO_MIN_JERSEY   = 280.0
PESO_MAX_JERSEY   = 500.0


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
#  HELPER INTERNO — subconsulta última medición
# ════════════════════════════════════════════════════════

def _subquery_ultima_medicion(db: Session, animal_ids: Optional[list] = None):
    """
    Devuelve subquery con la última fecha de medición por animal.
    Si animal_ids es None → todas las mediciones (para admin).
    """
    q = db.query(
        Medicion.animal_id,
        func.max(Medicion.fecha_medicion).label("ultima_fecha")
    )
    if animal_ids is not None:
        q = q.filter(Medicion.animal_id.in_(animal_ids))
    return q.group_by(Medicion.animal_id).subquery()


def _filtro_alerta():
    """
    Filtro SQLAlchemy unificado para condición de alerta.
    Usado igual en contadores y en el endpoint de listado.
    """
    return or_(
        Medicion.bcs < BCS_ALERTA,
        Medicion.peso_estimado_kg < PESO_MIN_JERSEY,
        Medicion.peso_estimado_kg > PESO_MAX_JERSEY,
    )


# ════════════════════════════════════════════════════════
#  HELPERS PÚBLICOS (usados por dashboard y alertas)
# ════════════════════════════════════════════════════════

def _contar_animales_en_alerta(db: Session) -> int:
    """Contador admin — todas las mediciones."""
    sub = _subquery_ultima_medicion(db)
    return db.query(func.count(Medicion.id)).join(
        sub,
        and_(
            Medicion.animal_id == sub.c.animal_id,
            Medicion.fecha_medicion == sub.c.ultima_fecha,
        )
    ).filter(_filtro_alerta()).scalar() or 0


def _contar_animales_en_alerta_ganadero(db: Session, animal_ids: list) -> int:
    """Contador ganadero — solo sus animales."""
    if not animal_ids:
        return 0
    sub = _subquery_ultima_medicion(db, animal_ids)
    return db.query(func.count(Medicion.id)).join(
        sub,
        and_(
            Medicion.animal_id == sub.c.animal_id,
            Medicion.fecha_medicion == sub.c.ultima_fecha,
        )
    ).filter(_filtro_alerta()).scalar() or 0


# ════════════════════════════════════════════════════════
#  HU-02 — LOG DE AUDITORÍA (solo Admin)
# ════════════════════════════════════════════════════════

@router.get("/auditoria", response_model=list[AuditoriaLogResponse])
def listar_logs_auditoria(
    usuario_email: Optional[str] = Query(None),
    accion: Optional[AccionAuditoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    tabla: Optional[str] = Query(None),
    limite: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
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
        log_dict = AuditoriaLogResponse.model_validate(log).model_dump()
        if log_dict.get("usuario_email"):
            try:
                log_dict["usuario_email"] = decrypt(log_dict["usuario_email"])
            except Exception:
                pass
        logs_formateados.append(log_dict)

    return logs_formateados


# ════════════════════════════════════════════════════════
#  HU-03 — DASHBOARD ADMINISTRATIVO
# ════════════════════════════════════════════════════════

@router.get("/admin", response_model=DashboardAdminResponse)
def dashboard_admin(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_admin),
):
    hoy_inicio = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return DashboardAdminResponse(
        total_usuarios    = db.query(func.count(Usuario.id)).scalar() or 0,
        usuarios_activos  = db.query(func.count(Usuario.id)).filter(Usuario.activo == True).scalar() or 0,
        total_ganaderos   = db.query(func.count(Usuario.id)).filter(Usuario.rol == RolUsuario.GANADERO).scalar() or 0,
        total_bovinos     = db.query(func.count(Animal.id)).scalar() or 0,
        total_evaluaciones= db.query(func.count(Medicion.id)).scalar() or 0,
        evaluaciones_hoy  = db.query(func.count(Medicion.id)).filter(
            Medicion.fecha_medicion >= hoy_inicio
        ).scalar() or 0,
        animales_en_alerta= _contar_animales_en_alerta(db),
    )


# ════════════════════════════════════════════════════════
#  HU-11 — DASHBOARD GANADERO
# ════════════════════════════════════════════════════════

@router.get("/ganadero", response_model=DashboardGanaderoResponse)
def dashboard_ganadero(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy_inicio = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    hato_ids = [
        h.id for h in db.query(Hato.id).filter(
            Hato.propietario_id == current_user.id,
            Hato.activo == True,
        ).all()
    ]
    if not hato_ids:
        return DashboardGanaderoResponse(
            total_animales=0, evaluaciones_hoy=0, animales_en_alerta=0,
            bcs_promedio=None, peso_promedio_kg=None, total_hatos=0,
        )

    animal_ids = [
        a.id for a in db.query(Animal.id).filter(
            Animal.hato_id.in_(hato_ids)
        ).all()
    ]

    evaluaciones_hoy = db.query(func.count(Medicion.id)).filter(
        Medicion.animal_id.in_(animal_ids),
        Medicion.fecha_medicion >= hoy_inicio,
    ).scalar() or 0

    stats = db.query(
        func.avg(Medicion.bcs).label("bcs_prom"),
        func.avg(Medicion.peso_estimado_kg).label("peso_prom"),
    ).filter(Medicion.animal_id.in_(animal_ids)).first()

    return DashboardGanaderoResponse(
        total_animales     = len(animal_ids),
        evaluaciones_hoy   = evaluaciones_hoy,
        animales_en_alerta = _contar_animales_en_alerta_ganadero(db, animal_ids),
        bcs_promedio       = round(stats.bcs_prom, 2) if stats and stats.bcs_prom else None,
        peso_promedio_kg   = round(stats.peso_prom, 1) if stats and stats.peso_prom else None,
        total_hatos        = len(hato_ids),
    )


# ════════════════════════════════════════════════════════
#  HU-13 — ANIMALES EN ALERTA (listado con detalle)
# ════════════════════════════════════════════════════════

@router.get("/alertas", response_model=list[AnimalAlertaItem])
def animales_en_alerta(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Listado de animales en alerta.

    - ADMIN  → considera TODOS los animales del sistema, igual que el
      contador `_contar_animales_en_alerta` usado en /dashboard/admin.
      (FIX: antes este endpoint siempre filtraba por
      Hato.propietario_id == current_user.id, así que un admin que no
      es propietario de ningún hato veía la lista vacía aunque el
      contador del KPI mostrara animales en alerta.)
    - GANADERO → solo los animales de sus propios hatos activos,
      igual que antes.

    Usa EXACTAMENTE los mismos criterios que los contadores del dashboard:
      - BCS < 2.5
      - Peso < 280 kg  (mínimo Jersey)
      - Peso > 500 kg  (máximo Jersey hembras)
    Solo considera la ÚLTIMA medición de cada animal.
    """
    if current_user.rol == RolUsuario.ADMIN:
        animal_ids = [a.id for a in db.query(Animal.id).all()]
    else:
        hato_ids = [
            h.id for h in db.query(Hato.id).filter(
                Hato.propietario_id == current_user.id,
                Hato.activo == True,
            ).all()
        ]
        if not hato_ids:
            return []

        animal_ids = [
            a.id for a in db.query(Animal.id).filter(
                Animal.hato_id.in_(hato_ids)
            ).all()
        ]

    if not animal_ids:
        return []

    # Última medición por animal — misma subquery que el contador
    sub = _subquery_ultima_medicion(db, animal_ids)

    # Aplicar el mismo filtro unificado
    ultimas = (
        db.query(Medicion)
        .join(
            sub,
            and_(
                Medicion.animal_id == sub.c.animal_id,
                Medicion.fecha_medicion == sub.c.ultima_fecha,
            )
        )
        .filter(_filtro_alerta())        # ← mismo filtro que el contador
        .all()
    )

    resultado = []
    for med in ultimas:
        animal = db.query(Animal).filter(Animal.id == med.animal_id).first()
        if not animal:
            continue
        hato = db.query(Hato).filter(Hato.id == animal.hato_id).first()

        motivos = []
        if med.bcs is not None and med.bcs < BCS_ALERTA:
            motivos.append(
                f"BCS {med.bcs:.2f} — por debajo del mínimo ({BCS_ALERTA})"
            )
        if med.peso_estimado_kg is not None:
            if med.peso_estimado_kg < PESO_MIN_JERSEY:
                motivos.append(
                    f"Peso {med.peso_estimado_kg:.1f} kg — bajo el rango Jersey ({PESO_MIN_JERSEY:.0f} kg)"
                )
            elif med.peso_estimado_kg > PESO_MAX_JERSEY:
                motivos.append(
                    f"Peso {med.peso_estimado_kg:.1f} kg — sobre el rango Jersey ({PESO_MAX_JERSEY:.0f} kg)"
                )

        resultado.append(AnimalAlertaItem(
            animal_id    = animal.id,
            arete        = animal.arete,
            nombre       = animal.nombre,
            hato_nombre  = hato.nombre if hato else "Sin hato",
            ultimo_bcs   = med.bcs,
            ultimo_peso_kg = med.peso_estimado_kg,
            motivo       = " | ".join(motivos),
        ))

    return resultado