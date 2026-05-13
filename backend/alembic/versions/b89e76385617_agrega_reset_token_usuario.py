"""agrega_reset_token_usuario

Revision ID: b89e76385617
Revises: a1b2c3d4e5f6
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b89e76385617'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fíjate bien que aquí diga add_column y NO create_table
    op.add_column('usuarios',
        sa.Column('reset_token', sa.String(length=255), nullable=True),
        schema='auth'
    )

def downgrade() -> None:
    op.drop_column('usuarios', 'reset_token', schema='auth')