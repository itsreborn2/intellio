"""add_content_type_to_stockeasy_chat_messages

Revision ID: 1b36eba35aa1
Revises: a1d80e8c029a
Create Date: 2025-04-15 02:59:20.209747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b36eba35aa1'
down_revision: Union[str, None] = 'a1d80e8c029a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 누락된 content_type 컬럼 추가
    op.add_column(
        'stockeasy_chat_messages',
        sa.Column('content_type', sa.String(50), nullable=False, server_default='text', comment='메시지 콘텐츠 타입 (text, image, chart, file, card 등)'),
        schema='stockeasy'
    )


def downgrade() -> None:
    # 컬럼 삭제 (롤백 시)
    op.drop_column('stockeasy_chat_messages', 'content_type', schema='stockeasy')
