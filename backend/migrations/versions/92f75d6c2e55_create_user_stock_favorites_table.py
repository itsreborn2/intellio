"""create_user_stock_favorites_table

Revision ID: 92f75d6c2e55
Revises: f68e5e33f876
Create Date: 2025-07-25 00:02:18.332932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f75d6c2e55'
down_revision: Union[str, None] = 'f68e5e33f876'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_stock_favorites 테이블 생성
    op.create_table(
        'user_stock_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('stock_code', sa.String(length=20), nullable=False),
        sa.Column('stock_name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='기본'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('memo', sa.Text(), nullable=True),
        # Base 클래스의 timestamp 컬럼들을 명시적으로 추가 (Alembic에서는 상속이 자동으로 처리되지 않음)
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)")),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='stockeasy'
    )
    
    # 2. 필수 인덱스 생성 (성능 핵심)
    # 사용자별 카테고리 내 순서 조회용
    op.create_index(
        'idx_user_category_display',
        'user_stock_favorites',
        ['user_id', 'category', 'display_order'],
        schema='stockeasy'
    )
    
    # 사용자별 종목코드와 카테고리 조합의 유니크 제약
    op.create_index(
        'idx_user_stock_category_unique',
        'user_stock_favorites',
        ['user_id', 'stock_code', 'category'],
        unique=True,
        schema='stockeasy'
    )
    
    # 3. 분석용 인덱스
    # 종목코드와 종목명으로 검색용
    op.create_index(
        'idx_stock_code_name',
        'user_stock_favorites',
        ['stock_code', 'stock_name'],
        schema='stockeasy'
    )


def downgrade() -> None:
    # 인덱스 삭제
    op.drop_index('idx_stock_code_name', table_name='user_stock_favorites', schema='stockeasy')
    op.drop_index('idx_user_stock_category_unique', table_name='user_stock_favorites', schema='stockeasy')
    op.drop_index('idx_user_category_display', table_name='user_stock_favorites', schema='stockeasy')
    
    # 테이블 삭제
    op.drop_table('user_stock_favorites', schema='stockeasy')
