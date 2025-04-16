"""add_agent_results_column_to_stockeasy_chat_messages

Revision ID: 37beda2499cc
Revises: 4b7d7dff445b
Create Date: 2025-04-15 19:55:17.043802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '37beda2499cc'
down_revision: Union[str, None] = '4b7d7dff445b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 에이전트 결과를 저장할 JSONB 타입 칼럼 추가 - stockeasy_chat_messages
    op.add_column(
        'stockeasy_chat_messages', 
        sa.Column(
            'agent_results', 
            postgresql.JSONB(astext_type=sa.Text()), 
            nullable=True,
            comment='에이전트 처리 결과 데이터'
        ),
        schema='stockeasy'
    )
    
    # 에이전트 결과를 저장할 JSONB 타입 칼럼 추가 - stockeasy_chat_sessions
    op.add_column(
        'stockeasy_chat_sessions',
        sa.Column(
            'agent_results', 
            postgresql.JSONB(astext_type=sa.Text()), 
            nullable=True,
            comment='세션의 에이전트 처리 결과 데이터'
        ),
        schema='stockeasy'
    )
    
    # stockeasy_chat_sessions 테이블에 종목 관련 칼럼 추가
    op.add_column(
        'stockeasy_chat_sessions',
        sa.Column(
            'stock_code',
            sa.String(20),
            nullable=True,
            comment='종목 코드'
        ),
        schema='stockeasy'
    )
    
    op.add_column(
        'stockeasy_chat_sessions',
        sa.Column(
            'stock_name',
            sa.String(100),
            nullable=True,
            comment='종목명'
        ),
        schema='stockeasy'
    )
    
    op.add_column(
        'stockeasy_chat_sessions',
        sa.Column(
            'stock_info',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='종목 관련 추가 정보 (업종, 시가총액 등)'
        ),
        schema='stockeasy'
    )
    
    # stock_code에 인덱스 추가
    op.create_index(
        'ix_stockeasy_chat_sessions_stock_code',
        'stockeasy_chat_sessions',
        ['stock_code'],
        schema='stockeasy'
    )


def downgrade() -> None:
    # 추가한 칼럼 제거 - stockeasy_chat_messages
    op.drop_column('stockeasy_chat_messages', 'agent_results', schema='stockeasy')
    
    # 인덱스 제거 - stockeasy_chat_sessions
    op.drop_index('ix_stockeasy_chat_sessions_stock_code', table_name='stockeasy_chat_sessions', schema='stockeasy')
    
    # 추가한 칼럼 제거 - stockeasy_chat_sessions
    op.drop_column('stockeasy_chat_sessions', 'agent_results', schema='stockeasy')
    op.drop_column('stockeasy_chat_sessions', 'stock_info', schema='stockeasy')
    op.drop_column('stockeasy_chat_sessions', 'stock_name', schema='stockeasy')
    op.drop_column('stockeasy_chat_sessions', 'stock_code', schema='stockeasy')
