"""add_links_and_original_created_at_to_telegram_messages

Revision ID: 04d1ee83c9da
Revises: dc00eb69d099
Create Date: 2025-01-31 03:08:29.243252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04d1ee83c9da'
down_revision: Union[str, None] = 'dc00eb69d099'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
