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
    # content_type 컬럼이 존재하는지 확인
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('stockeasy_chat_messages', schema='stockeasy')]
    
    # 컬럼이 없을 때만 추가
    if 'content_type' not in columns:
        op.add_column(
            'stockeasy_chat_messages',
            sa.Column('content_type', sa.String(50), nullable=False, server_default='text', comment='메시지 콘텐츠 타입 (text, image, chart, file, card 등)'),
            schema='stockeasy'
        )


def downgrade() -> None:
    # 컬럼 삭제 (롤백 시)
    op.drop_column('stockeasy_chat_messages', 'content_type', schema='stockeasy')
