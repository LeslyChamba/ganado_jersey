"""mover_tablas_a_esquemas

Revision ID: c5fa00831e83
Revises: 78a85b04434c
Create Date: 2026-03-29 10:31:17.304264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5fa00831e83'
down_revision: Union[str, None] = '78a85b04434c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
