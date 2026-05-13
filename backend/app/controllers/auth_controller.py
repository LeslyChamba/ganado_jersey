# app/controllers/auth_controller.py
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.utils_email import enviar_correo_recuperacion
from app.db.database import get_db
from app.models.models import Usuario, AccionAuditoria
from app.schemas.schemas import (
    UsuarioCreate, LoginRequest, TokenResponse,
    UsuarioResponse, RefreshRequest
)
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
    oauth2_scheme
)
from app.services.auditoria_service import registrar_log

MAX_INTENTOS_FALLIDOS = 5
BLOQUEO_MINUTOS       = 15
INACTIVIDAD_MINUTOS   = 30

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ─── Esquemas locales ────────────────────────────────────────────────────────

class SolicitarRecuperacionRequest(BaseModel):
    email: EmailStr

class ConfirmarRecuperacionRequest(BaseModel):
    token:           str
    nueva_password:  str


# ─── Recuperación de contraseña ──────────────────────────────────────────────

@router.post("/recuperar-password")
def solicitar_recuperacion(
    datos: SolicitarRecuperacionRequest,
    db:    Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()

    if usuario:
        token_seguro       = secrets.token_urlsafe(32)
        usuario.reset_token = token_seguro
        db.commit()
        try:
            enviar_correo_recuperacion(datos.email, token_seguro)
        except Exception as e:
            print(f"❌ ERROR SMTP: {e}")

    # Respuesta siempre igual para no revelar si el correo existe
    return {"mensaje": "Si el correo existe, se enviará un enlace."}


@router.post("/reset-password")
def confirmar_recuperacion(
    datos: ConfirmarRecuperacionRequest,
    db:    Session = Depends(get_db),
):
    if len(datos.nueva_password) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")

    usuario = db.query(Usuario).filter(Usuario.reset_token == datos.token).first()
    if not usuario:
        raise HTTPException(400, "El enlace es inválido o ya expiró.")

    usuario.password_hash = get_password_hash(datos.nueva_password)
    usuario.reset_token   = None
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente"}


# ─── Registro ────────────────────────────────────────────────────────────────

@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    datos:   UsuarioCreate,
    request: Request,
    db:      Session = Depends(get_db),
):
    if db.query(Usuario).filter(Usuario.email == datos.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo electrónico",
        )

    usuario = Usuario(
        email         = datos.email,
        password_hash = get_password_hash(datos.password),
        nombre        = datos.nombre,
        apellido      = datos.apellido,
        telefono      = datos.telefono,
        rol           = datos.rol,
    )
    db.add(usuario); db.commit(); db.refresh(usuario)

    registrar_log(
        db=db, accion=AccionAuditoria.CREAR,
        usuario_id=usuario.id, usuario_email=usuario.email,
        tabla="usuarios", registro_id=usuario.id,
        despues={"email": usuario.email, "rol": str(usuario.rol)},
        ip=request.client.host, detalle="Nuevo usuario registrado",
    )
    return usuario


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(
    datos:   LoginRequest,
    request: Request,
    db:      Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contacte al administrador para habilitar su acceso.",
        )

    ahora = datetime.now(timezone.utc)
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        segundos = int((usuario.bloqueado_hasta - ahora).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Cuenta bloqueada. Intente en {segundos} segundos.",
        )

    if not verify_password(datos.password, usuario.password_hash):
        usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
        if usuario.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
            usuario.bloqueado_hasta   = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
            usuario.intentos_fallidos = 0
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos. Cuenta bloqueada por {BLOQUEO_MINUTOS} minutos.",
            )
        db.commit()
        restantes = MAX_INTENTOS_FALLIDOS - usuario.intentos_fallidos
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Correo o contraseña incorrectos. Intentos restantes: {restantes}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Login exitoso
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta   = None
    usuario.ultimo_acceso     = ahora
    db.commit()

    token_data = {
        "sub":         str(usuario.id),
        "email":       usuario.email,
        "rol":         usuario.rol,
        "last_active": ahora.isoformat(),
    }

    registrar_log(
        db=db, accion=AccionAuditoria.LOGIN,
        usuario_id=usuario.id, usuario_email=usuario.email,
        ip=request.client.host, detalle="Login exitoso",
    )

    return TokenResponse(
        access_token  = create_access_token(token_data),
        refresh_token = create_refresh_token(token_data),
        usuario       = UsuarioResponse.model_validate(usuario),
    )


# ─── Refresh ─────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    datos: RefreshRequest,
    db:    Session = Depends(get_db),
):
    payload = decode_token(datos.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido",
        )

    usuario = db.query(Usuario).filter(Usuario.id == payload.get("sub")).first()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )

    token_data = {
        "sub":   str(usuario.id),
        "email": usuario.email,
        "rol":   usuario.rol,
    }

    return TokenResponse(
        access_token  = create_access_token(token_data),
        refresh_token = create_refresh_token(token_data),
        usuario       = UsuarioResponse.model_validate(usuario),
    )


# ─── Dependencies ────────────────────────────────────────────────────────────

def get_current_user(
    token: str     = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> Usuario:
    payload    = decode_token(token)
    usuario_id = payload.get("sub")

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario",
        )

    last_active_str = payload.get("last_active")
    if last_active_str:
        try:
            last_active = datetime.fromisoformat(last_active_str)
            if datetime.now(timezone.utc) - last_active > timedelta(minutes=INACTIVIDAD_MINUTOS):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sesión expirada por inactividad. Inicie sesión nuevamente.",
                )
        except ValueError:
            pass

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )
    return usuario


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    from app.models.models import RolUsuario
    if current_user.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user