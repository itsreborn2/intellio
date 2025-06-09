"""채팅_세션_성능_최적화_인덱스_추가

Revision ID: f68e5e33f876
Revises: 4e0862caa77d
Create Date: 2025-06-09 07:30:24.950050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f68e5e33f876'
down_revision: Union[str, None] = '4e0862caa77d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """채팅 세션 성능 최적화를 위한 복합 인덱스를 추가합니다."""
    
    # 사용자별 세션을 최신순으로 정렬 조회할 때 성능 최적화
    # WHERE user_id = ? ORDER BY updated_at DESC 쿼리 최적화
    op.create_index(
        'ix_stockeasy_chat_sessions_user_id_updated_at',
        'stockeasy_chat_sessions',
        ['user_id', 'updated_at'],
        schema='stockeasy'
    )
    
    # 사용자별 활성/비활성 세션 필터링 성능 최적화  
    # WHERE user_id = ? AND is_active = ? 쿼리 최적화
    op.create_index(
        'ix_stockeasy_chat_sessions_user_id_is_active',
        'stockeasy_chat_sessions', 
        ['user_id', 'is_active'],
        schema='stockeasy'
    )


def downgrade() -> None:
    """추가된 인덱스를 제거합니다."""
    
    # 인덱스 제거 (역순으로)
    op.drop_index(
        'ix_stockeasy_chat_sessions_user_id_is_active',
        table_name='stockeasy_chat_sessions',
        schema='stockeasy'
    )
    
    op.drop_index(
        'ix_stockeasy_chat_sessions_user_id_updated_at', 
        table_name='stockeasy_chat_sessions',
        schema='stockeasy'
    )
