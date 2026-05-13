"""add login security fields to usuarios

Revision ID: a1b2c3d4e5f6
Revises: c5fa00831e83
Create Date: 2026-03-31

Agrega campos para:
- HU-14: bloqueo tras 5 intentos fallidos
- HU-14: expiración de sesión por inactividad
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'c5fa00831e83'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usuarios',
        sa.Column('intentos_fallidos', sa.Integer(), nullable=False, server_default='0'),
        schema='auth'
    )
    op.add_column('usuarios',
        sa.Column('bloqueado_hasta', sa.DateTime(timezone=True), nullable=True),
        schema='auth'
    )
    op.add_column('usuarios',
        sa.Column('ultimo_acceso', sa.DateTime(timezone=True), nullable=True),
        schema='auth'
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'ultimo_acceso', schema='auth')
    op.drop_column('usuarios', 'bloqueado_hasta', schema='auth')
    op.drop_column('usuarios', 'intentos_fallidos', schema='auth')
