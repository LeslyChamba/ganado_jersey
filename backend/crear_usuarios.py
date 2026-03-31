from app.db.database import SessionLocal
from app.models.models import Usuario, RolUsuario
from app.core.security import get_password_hash

db = SessionLocal()

usuario = Usuario(
    email         = "lesly15chamba@gmail.com",
    password_hash = get_password_hash("vacas2026"),
    nombre        = "Lesly",
    apellido      = "Chamba",
    rol           = RolUsuario.ADMIN,
    activo        = True,
    
    email         = "criaderoelpuente@gmail.com",
    password_hash = get_password_hash("vacas2026"),
    nombre        = "Fabian",
    apellido      = "Alzamora",
    rol           = RolUsuario.GANADERO,
    activo        = True,
)

db.add(usuario)
db.commit()
db.refresh(usuario)
print(f"✅ Usuario creado: {usuario.email}")
db.close()