"""add_forwarded_fields_to_telegram_messages

수동 마이그레이션: 텔레그램 메시지 테이블에 전달된 메시지 관련 필드 추가

Revision ID: abcdef12345
Revises: b63e97bffd70
Create Date: 2025-03-29 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abcdef12345'
down_revision: Union[str, None] = 'b63e97bffd70'  # 마지막 마이그레이션 ID로 수정
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 텔레그램 메시지 테이블에 전달 메시지 관련 필드 추가
    op.add_column('telegram_messages', sa.Column('is_forwarded', sa.Boolean(), nullable=True))
    op.add_column('telegram_messages', sa.Column('forward_from_name', sa.String(), nullable=True))
    op.add_column('telegram_messages', sa.Column('forward_from_id', sa.String(), nullable=True))
    
    # NULL 값을 False로 업데이트
    op.execute("UPDATE telegram_messages SET is_forwarded = FALSE WHERE is_forwarded IS NULL")
    
    # NOT NULL 제약조건 설정
    op.alter_column('telegram_messages', 'is_forwarded',
                   existing_type=sa.Boolean(),
                   nullable=False,
                   server_default=sa.text('false'))


def downgrade() -> None:
    # 추가된 컬럼 제거
    op.drop_column('telegram_messages', 'forward_from_id')
    op.drop_column('telegram_messages', 'forward_from_name')
    op.drop_column('telegram_messages', 'is_forwarded') 