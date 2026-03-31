
from app.db.database import SessionLocal
from app.models.models import Usuario
db = SessionLocal()
usuarios = db.query(Usuario).all()
for u in usuarios:
    print(f'Email: {u.email} | Activo: {u.activo} | Rol: {u.rol}')
db.close()

