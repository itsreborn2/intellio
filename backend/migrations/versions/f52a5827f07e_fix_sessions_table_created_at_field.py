"""fix_sessions_table_created_at_field

Revision ID: f52a5827f07e
Revises: 42ec716857fb
Create Date: 2025-02-20 17:55:16.168854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f52a5827f07e'
down_revision: Union[str, None] = '42ec716857fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
