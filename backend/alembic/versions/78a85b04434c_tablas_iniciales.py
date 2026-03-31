"""tablas iniciales

Revision ID: 78a85b04434c
Revises: 
Create Date: 2026-03-25 18:01:06.842863

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78a85b04434c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # 1. Crear esquemas
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS ganaderia")
    op.execute("CREATE SCHEMA IF NOT EXISTS reportes")

    # 2. Mover tablas (el orden importa por las FK)
    op.execute("ALTER TABLE public.usuarios   SET SCHEMA auth")
    op.execute("ALTER TABLE public.hatos      SET SCHEMA ganaderia")
    op.execute("ALTER TABLE public.animales   SET SCHEMA ganaderia")
    op.execute("ALTER TABLE public.mediciones SET SCHEMA ganaderia")
    op.execute("ALTER TABLE public.reportes   SET SCHEMA reportes")

def downgrade():
    op.execute("ALTER TABLE auth.usuarios         SET SCHEMA public")
    op.execute("ALTER TABLE ganaderia.hatos        SET SCHEMA public")
    op.execute("ALTER TABLE ganaderia.animales     SET SCHEMA public")
    op.execute("ALTER TABLE ganaderia.mediciones   SET SCHEMA public")
    op.execute("ALTER TABLE reportes.reportes      SET SCHEMA public")

    op.execute("DROP SCHEMA IF EXISTS auth")
    op.execute("DROP SCHEMA IF EXISTS ganaderia")
    op.execute("DROP SCHEMA IF EXISTS reportes")