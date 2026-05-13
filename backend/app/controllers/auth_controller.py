import secrets
from app.core.utils_email import enviar_correo_recuperacion
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.encryption import encrypt , decrypt
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
from app.core.encryption import decrypt
MAX_INTENTOS_FALLIDOS = 5
BLOQUEO_MINUTOS = 15
INACTIVIDAD_MINUTOS = 30

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# --- Asegúrate de tener estas importaciones arriba ---
import secrets
from app.core.utils_email import enviar_correo_recuperacion
from pydantic import BaseModel, EmailStr

# --- Esquemas para la petición ---
class SolicitarRecuperacionRequest(BaseModel):
    email: EmailStr

class ConfirmarRecuperacionRequest(BaseModel):
    token: str
    nueva_password: str

# --- Endpoint 1: Solicitar ---
@router.post("/recuperar-password")
def solicitar_recuperacion(datos: SolicitarRecuperacionRequest, db: Session = Depends(get_db)):
    # Buscamos al usuario (desencriptando en memoria para encontrar el email)
    usuarios = db.query(Usuario).all()
    usuario = next((u for u in usuarios if decrypt(u.email) == datos.email), None)
    
    if not usuario:
        return {"mensaje": "Si el correo existe, se enviará un enlace."}

    token_seguro = secrets.token_urlsafe(32)
    usuario.reset_token = token_seguro
    db.commit()

    email_limpio = decrypt(usuario.email) 
    
    try:
        enviar_correo_recuperacion(email_limpio, token_seguro)
        print(f"✅ CORREO ENVIADO A: {email_limpio}") # Revisa esto en tu terminal
    except Exception as e:
        print(f"❌ ERROR SMTP: {e}")

    return {"mensaje": "Si el correo existe, se enviará un enlace."}

# --- Endpoint 2: Resetear ---
@router.post("/reset-password")
def confirmar_recuperacion(datos: ConfirmarRecuperacionRequest, db: Session = Depends(get_db)):
    if len(datos.nueva_password) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")

    usuario = db.query(Usuario).filter(Usuario.reset_token == datos.token).first()
    if not usuario:
        raise HTTPException(400, "El enlace es inválido o ya expiró.")

    usuario.password_hash = get_password_hash(datos.nueva_password)
    usuario.reset_token = None
    db.commit()
    return {"mensaje": "Contraseña actualizada correctamente"}

@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(datos: UsuarioCreate, request: Request, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.email == encrypt(datos.email)).first()
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
    # 1. TRAER TODOS LOS USUARIOS (O FILTRAR POR ESTADO ACTIVO)
    # No podemos usar filter(email == ...) por la naturaleza de Fernet
    usuarios_candidatos = db.query(Usuario).all()
    
    usuario = None
    
    # 2. BUSCAR COINCIDENCIA DESENCRIPTANDO EN MEMORIA
    for u in usuarios_candidatos:
        try:
            if decrypt(u.email) == datos.email:
                usuario = u
                break
        except Exception:
            continue

    # Usuario no existe — no revelar detalle
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    #  Verificar primero si la cuenta está INACTIVA
    # Es mejor informar esto antes de validar bloqueos o contraseñas
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contacte al administrador para habilitar su acceso."
        )
    # Verificar si está bloqueado temporalmente
    ahora = datetime.now(timezone.utc)
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        segundos = int((usuario.bloqueado_hasta - ahora).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Cuenta bloqueada por demasiados intentos fallidos. Intente en {segundos} segundos.",
        )

    # Verificar contraseña (Usamos password_hash que NO es Fernet, sino Hash, por eso funciona directo)
    if not verify_password(datos.password, usuario.password_hash):
        usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
        if usuario.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
            usuario.intentos_fallidos = 0
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Cuenta bloqueada por {BLOQUEO_MINUTOS} minutos.",
            )
        db.commit()
        restantes = MAX_INTENTOS_FALLIDOS - usuario.intentos_fallidos
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Correo o contraseña incorrectos. Intentos restantes: {restantes}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada. Contacte al administrador."
        )

    # Login exitoso: resetear intentos y actualizar último acceso
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    db.commit()

    # IMPORTANTE: Usamos decrypt para meter el email real en el JWT
    email_real = decrypt(usuario.email)
    
    token_data = {
        "sub": str(usuario.id), 
        "email": email_real, 
        "rol": usuario.rol,
        "last_active": ahora.isoformat()
    }

    registrar_log(
        db=db,
        accion=AccionAuditoria.LOGIN,
        usuario_id=usuario.id,
        usuario_email=email_real,
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

    token_data = {"sub": str(usuario.id), "email": decrypt(usuario.email), "rol": usuario.rol}

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

    # Verificar inactividad de 30 minutos (basado en la marca en el token)
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