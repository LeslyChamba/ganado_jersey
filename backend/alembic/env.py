from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

# ── Hacer visible el paquete app ──────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings          # tu configuración con .env
from app.db.database import Base              # tu Base declarativa
import app.models.models                      # importar modelos para que Alembic los detecte

# ── Config de Alembic ────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inyectar la URL desde tu settings (lee el .env automáticamente)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Metadata de tus modelos — Alembic la compara contra la BD real
target_metadata = Base.metadata


# ── Modo offline (genera SQL sin conectar) ───────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Modo online (conecta y aplica directo) ───────────────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,        # detecta cambios de tipo (ej: String(50) → String(100))
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()