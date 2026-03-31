from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings


# ─── Engine ─────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # Verifica conexión antes de usarla
    pool_size=10,                # Conexiones en el pool
    max_overflow=20,             # Conexiones adicionales bajo carga
    pool_recycle=3600,           # Reciclar conexiones cada hora
    echo=settings.DEBUG,         # Log SQL en desarrollo
)

# ─── Session factory ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ─── Base declarativa para los modelos ORM ──────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─── Dependency: sesión de BD por request ───────────────────────────────────
def get_db():
    """
    Dependency injection para FastAPI.
    Garantiza que la sesión se cierre al terminar el request.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()   # ← NUEVO: deshace cambios si algo falla
        raise           # ← re-lanza el error para que FastAPI lo maneje
    finally:
        db.close()
