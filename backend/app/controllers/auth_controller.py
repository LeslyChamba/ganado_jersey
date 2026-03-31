from fastapi import APIRouter, Depends, HTTPException, status, Request  # ← agrega Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import Usuario, AccionAuditoria              # ← agrega AccionAuditoria
from app.schemas.schemas import (
    UsuarioCreate, LoginRequest, TokenResponse,
    UsuarioResponse, RefreshRequest
)
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
    oauth2_scheme
)
from app.services.auditoria_service import registrar_log            # ← agrega esto

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(datos: UsuarioCreate, request: Request, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con ese correo electrónico"
        )

    usuario = Usuario(
        email=datos.email,
        password_hash=get_password_hash(datos.password),
        nombre=datos.nombre,
        apellido=datos.apellido,
        telefono=datos.telefono,
        rol=datos.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # ── Log de registro ──────────────────────────────────────────
    registrar_log(
        db=db,
        accion=AccionAuditoria.CREAR,
        usuario_id=usuario.id,
        usuario_email=usuario.email,
        tabla="usuarios",
        registro_id=usuario.id,
        despues={"email": usuario.email, "rol": str(usuario.rol)},
        ip=request.client.host,
        detalle="Nuevo usuario registrado"
    )
    return usuario


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, request: Request, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()

    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contacte al administrador."
        )

    token_data = {"sub": str(usuario.id), "email": usuario.email, "rol": usuario.rol}

    # ── Log de login ─────────────────────────────────────────────
    registrar_log(
        db=db,
        accion=AccionAuditoria.LOGIN,
        usuario_id=usuario.id,
        usuario_email=usuario.email,
        ip=request.client.host,
        detalle="Login exitoso"
    )

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(datos: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(datos.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido"
        )

    usuario_id = payload.get("sub")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado"
        )

    token_data = {"sub": str(usuario.id), "email": usuario.email, "rol": usuario.rol}

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        usuario=UsuarioResponse.model_validate(usuario),
    )


# ─── Dependencies ────────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    payload = decode_token(token)
    usuario_id = payload.get("sub")

    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario"
        )

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado"
        )
    return usuario


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    from app.models.models import RolUsuario
    if current_user.rol != RolUsuario.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user