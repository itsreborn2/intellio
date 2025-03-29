"""add_keywords_to_telegram_metadata

Revision ID: 94f4a7823be1
Revises: abcdef12345
Create Date: 2025-03-29 12:15:43.859445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94f4a7823be1'
down_revision: Union[str, None] = 'abcdef12345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
