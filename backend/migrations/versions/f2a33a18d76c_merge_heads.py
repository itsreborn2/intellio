"""merge heads

Revision ID: f2a33a18d76c
Revises: 2c7654b3d4c3, add_default_timestamps
Create Date: 2025-02-20 18:24:37.707021

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a33a18d76c'
down_revision: Union[str, None] = ('2c7654b3d4c3', 'add_default_timestamps')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
