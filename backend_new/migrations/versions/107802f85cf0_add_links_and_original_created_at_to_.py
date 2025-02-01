"""add_links_and_original_created_at_to_telegram_messages

Revision ID: 107802f85cf0
Revises: 04d1ee83c9da
Create Date: 2025-01-31 03:11:41.761615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '107802f85cf0'
down_revision: Union[str, None] = '04d1ee83c9da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
