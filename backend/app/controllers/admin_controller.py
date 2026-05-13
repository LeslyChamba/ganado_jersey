# app/controllers/admin_controller.py
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.controllers.auth_controller import require_admin
from app.db.database import get_db
from app.core.utils_email import enviar_correo_bienvenida
from app.models.models import (
    AccionAuditoria, Animal, Hato, Medicion, RolUsuario, Usuario
)
from app.services.auditoria_service import registrar_log

router = APIRouter(prefix="/admin", tags=["Administración de Usuarios"])


class UsuarioAdminCreate(BaseModel):
    email:    EmailStr
    password: str
    nombre:   str
    apellido: str
    telefono: Optional[str] = None
    rol:      RolUsuario    = RolUsuario.GANADERO

    @field_validator("password")
    @classmethod
    def password_minimo(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UsuarioAdminUpdate(BaseModel):
    nombre:   Optional[str]      = None
    apellido: Optional[str]      = None
    telefono: Optional[str]      = None
    email:    Optional[EmailStr] = None


class CambioRolRequest(BaseModel):
    rol: RolUsuario


class CambioEstadoRequest(BaseModel):
    activo: bool


class UsuarioAdminResponse(BaseModel):
    id:               uuid.UUID
    email:            str
    nombre:           str
    apellido:         str
    telefono:         Optional[str]
    rol:              RolUsuario
    activo:           bool
    total_hatos:      int = 0
    total_animales:   int = 0
    total_mediciones: int = 0

    model_config = {"from_attributes": True}


def _enriquecer_usuario(usuario: Usuario, db: Session) -> UsuarioAdminResponse:
    hato_ids = [
        h.id for h in db.query(Hato.id)
        .filter(Hato.propietario_id == usuario.id).all()
    ]
    total_hatos = len(hato_ids)

    total_animales = (
        db.query(func.count(Animal.id))
        .filter(Animal.hato_id.in_(hato_ids)).scalar() or 0
    ) if hato_ids else 0

    animal_ids = [
        a.id for a in db.query(Animal.id)
        .filter(Animal.hato_id.in_(hato_ids)).all()
    ] if hato_ids else []

    total_mediciones = (
        db.query(func.count(Medicion.id))
        .filter(Medicion.animal_id.in_(animal_ids)).scalar() or 0
    ) if animal_ids else 0

    r = UsuarioAdminResponse.model_validate(usuario)
    r.total_hatos      = total_hatos
    r.total_animales   = total_animales
    r.total_mediciones = total_mediciones
    return r


def _get_usuario_o_404(usuario_id: uuid.UUID, db: Session) -> Usuario:
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


@router.get("/usuarios", response_model=list[UsuarioAdminResponse])
def listar_usuarios(
    rol:    Optional[RolUsuario] = Query(None),
    activo: Optional[bool]       = Query(None),
    buscar: Optional[str]        = Query(None, description="Nombre o email"),
    db:     Session              = Depends(get_db),
    _:      Usuario              = Depends(require_admin),
):
    q = db.query(Usuario)
    if rol    is not None: q = q.filter(Usuario.rol    == rol)
    if activo is not None: q = q.filter(Usuario.activo == activo)
    if buscar:
        like = f"%{buscar}%"
        q = q.filter(
            (Usuario.nombre.ilike(like))
            | (Usuario.apellido.ilike(like))
            | (Usuario.email.ilike(like))
        )
    return [_enriquecer_usuario(u, db) for u in q.order_by(Usuario.nombre).all()]


@router.get("/usuarios/{usuario_id}", response_model=UsuarioAdminResponse)
def obtener_usuario(
    usuario_id: uuid.UUID,
    db:         Session = Depends(get_db),
    _:          Usuario = Depends(require_admin),
):
    return _enriquecer_usuario(_get_usuario_o_404(usuario_id, db), db)


@router.post("/usuarios", response_model=UsuarioAdminResponse, status_code=201)
def crear_usuario_admin(
    datos:   UsuarioAdminCreate,
    request: Request,
    db:      Session = Depends(get_db),
    admin:   Usuario = Depends(require_admin),
):
    if db.query(Usuario).filter(Usuario.email == datos.email).first():
        raise HTTPException(400, "Ya existe una cuenta con ese correo electrónico")

    nuevo = Usuario(
        email         = datos.email,
        password_hash = get_password_hash(datos.password),
        nombre        = datos.nombre,
        apellido      = datos.apellido,
        telefono      = datos.telefono,
        rol           = datos.rol,
        activo        = True,
    )
    db.add(nuevo); db.commit(); db.refresh(nuevo)

    registrar_log(
        db=db, accion=AccionAuditoria.CREAR,
        usuario_id=admin.id, usuario_email=admin.email,
        tabla="usuarios", registro_id=nuevo.id,
        despues={"email": nuevo.email, "rol": str(nuevo.rol)},
        ip=request.client.host,
        detalle=f"Admin creó usuario {nuevo.email} con rol {nuevo.rol}",
    )
    enviar_correo_bienvenida(
        email_destino=datos.email,
        nombre=datos.nombre,
        password_generada=datos.password
    )
    return _enriquecer_usuario(nuevo, db)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioAdminResponse)
def actualizar_usuario(
    usuario_id: uuid.UUID,
    datos:      UsuarioAdminUpdate,
    request:    Request,
    db:         Session = Depends(get_db),
    admin:      Usuario = Depends(require_admin),
):
    usuario = _get_usuario_o_404(usuario_id, db)
    antes   = {"nombre": usuario.nombre, "apellido": usuario.apellido,
                "email": usuario.email,  "telefono": usuario.telefono}

    if datos.email and datos.email != usuario.email:
        if db.query(Usuario).filter(Usuario.email == datos.email).first():
            raise HTTPException(400, "Ese correo ya está en uso")

    for campo, valor in datos.model_dump(exclude_none=True).items():
        setattr(usuario, campo, valor)
    db.commit(); db.refresh(usuario)

    registrar_log(
        db=db, accion=AccionAuditoria.MODIFICAR,
        usuario_id=admin.id, usuario_email=admin.email,
        tabla="usuarios", registro_id=usuario_id,
        antes=antes, despues=datos.model_dump(exclude_none=True),
        ip=request.client.host, detalle=f"Admin editó datos de {usuario.email}",
    )
    return _enriquecer_usuario(usuario, db)


@router.patch("/usuarios/{usuario_id}/rol", response_model=UsuarioAdminResponse)
def cambiar_rol(
    usuario_id: uuid.UUID,
    datos:      CambioRolRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    admin:      Usuario = Depends(require_admin),
):
    if usuario_id == admin.id:
        raise HTTPException(400, "No puedes cambiar tu propio rol")

    usuario     = _get_usuario_o_404(usuario_id, db)
    rol_previo  = usuario.rol
    usuario.rol = datos.rol
    db.commit(); db.refresh(usuario)

    registrar_log(
        db=db, accion=AccionAuditoria.MODIFICAR,
        usuario_id=admin.id, usuario_email=admin.email,
        tabla="usuarios", registro_id=usuario_id,
        antes={"rol": str(rol_previo)}, despues={"rol": str(datos.rol)},
        ip=request.client.host, detalle=f"Rol cambiado: {rol_previo} → {datos.rol}",
    )
    return _enriquecer_usuario(usuario, db)


@router.patch("/usuarios/{usuario_id}/estado", response_model=UsuarioAdminResponse)
def cambiar_estado(
    usuario_id: uuid.UUID,
    datos:      CambioEstadoRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    admin:      Usuario = Depends(require_admin),
):
    if usuario_id == admin.id and not datos.activo:
        raise HTTPException(400, "No puedes desactivar tu propia cuenta")

    usuario        = _get_usuario_o_404(usuario_id, db)
    estado_previo  = usuario.activo
    usuario.activo = datos.activo
    db.commit(); db.refresh(usuario)

    etiqueta = "activado" if datos.activo else "desactivado"
    registrar_log(
        db=db, accion=AccionAuditoria.MODIFICAR,
        usuario_id=admin.id, usuario_email=admin.email,
        tabla="usuarios", registro_id=usuario_id,
        antes={"activo": estado_previo}, despues={"activo": datos.activo},
        ip=request.client.host, detalle=f"Cuenta {etiqueta}: {usuario.email}",
    )
    return _enriquecer_usuario(usuario, db)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: uuid.UUID,
    request:    Request,
    db:         Session = Depends(get_db),
    admin:      Usuario = Depends(require_admin),
):
    if usuario_id == admin.id:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta")

    usuario = _get_usuario_o_404(usuario_id, db)

    if usuario.activo:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un usuario ACTIVO. Primero debe desactivar la cuenta."
        )
    if db.query(Hato).filter(
        Hato.propietario_id == usuario_id, Hato.activo == True
    ).first():
        raise HTTPException(
            400,
            "No se puede eliminar: el usuario tiene hatos activos. "
            "Desactívalos primero o reasígnalos."
        )

    from app.models.models import AuditoriaLog
    db.query(AuditoriaLog).filter(AuditoriaLog.usuario_id == usuario_id).update({"usuario_id": None})

    registrar_log(
        db=db, accion=AccionAuditoria.ELIMINAR,
        usuario_id=admin.id, usuario_email=admin.email,
        tabla="usuarios", registro_id=usuario_id,
        antes={"email": usuario.email, "rol": str(usuario.rol)},
        ip=request.client.host, detalle=f"Admin eliminó usuario {usuario.email}",
    )
    db.delete(usuario); db.commit()


@router.get("/bovinos/stats")
def stats_globales_bovinos(db: Session = Depends(get_db)):
    total = db.query(Animal).count()

    stats = db.query(
        func.avg(Medicion.peso_estimado_kg).label("peso_prom"),
        func.avg(Medicion.bcs).label("bcs_prom"),
        func.min(Medicion.peso_estimado_kg).label("peso_min"),
        func.max(Medicion.peso_estimado_kg).label("peso_max"),
    ).first()

    en_alerta = db.query(Medicion).filter(Medicion.bcs < 2.5).count()

    return {
        "total":        total,
        "peso_promedio": round(stats.peso_prom, 1) if stats.peso_prom else 0,
        "bcs_promedio":  round(stats.bcs_prom,  1) if stats.bcs_prom  else 0,
        "peso_min":      round(stats.peso_min,   1) if stats.peso_min  else 0,
        "peso_max":      round(stats.peso_max,   1) if stats.peso_max  else 0,
        "en_alerta":     en_alerta,
    }