"""add_telegram_document_fields

Revision ID: dc00eb69d099
Revises: a66f67c23883
Create Date: 2025-01-30 07:12:29.857976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc00eb69d099'
down_revision: Union[str, None] = 'a66f67c23883'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 이미 컬럼이 존재하므로 아무 작업도 하지 않음
    pass


def downgrade() -> None:
    # 이미 컬럼이 존재하므로 아무 작업도 하지 않음
    pass
