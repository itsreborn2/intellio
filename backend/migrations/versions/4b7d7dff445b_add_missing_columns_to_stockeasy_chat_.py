"""add_missing_columns_to_stockeasy_chat_messages

Revision ID: 4b7d7dff445b
Revises: 1b36eba35aa1
Create Date: 2025-04-15 11:05:47.375100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '4b7d7dff445b'
down_revision: Union[str, None] = '1b36eba35aa1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # message_data 컬럼 추가 (JSONB 타입)
    op.add_column(
        'stockeasy_chat_messages', 
        sa.Column('message_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True, 
                  comment='메시지 타입별 구조화된 데이터 (차트 데이터, 카드 정보 등)'),
        schema='stockeasy'
    )
    
    # data_url 컬럼 추가 (Text 타입)
    op.add_column(
        'stockeasy_chat_messages', 
        sa.Column('data_url', sa.Text(), nullable=True, 
                  comment='외부 리소스 URL (이미지, 차트 데이터 등)'),
        schema='stockeasy'
    )
    
    # message_metadata 컬럼 타입 확인 및 필요시 변경
    conn = op.get_bind()
    
    # 데이터 타입 확인을 위한 쿼리
    result = conn.execute(text("""
        SELECT data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'stockeasy' 
          AND table_name = 'stockeasy_chat_messages' 
          AND column_name = 'message_metadata'
    """)).fetchone()
    
    # 결과가 있고 타입이 jsonb가 아닌 경우에만 변경
    if result and result[0].lower() != 'jsonb':
        op.execute(
            """
            ALTER TABLE stockeasy.stockeasy_chat_messages 
            ALTER COLUMN message_metadata TYPE jsonb USING 
            CASE 
                WHEN message_metadata IS NULL THEN NULL
                WHEN message_metadata = '' THEN '{}'::jsonb
                ELSE message_metadata::jsonb 
            END
            """
        )


def downgrade() -> None:
    # 추가된 컬럼들 삭제
    op.drop_column('stockeasy_chat_messages', 'message_data', schema='stockeasy')
    op.drop_column('stockeasy_chat_messages', 'data_url', schema='stockeasy')
    
    # message_metadata 컬럼 타입 확인 및 필요시 변경
    conn = op.get_bind()
    
    # 데이터 타입 확인을 위한 쿼리
    result = conn.execute(text("""
        SELECT data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'stockeasy' 
          AND table_name = 'stockeasy_chat_messages' 
          AND column_name = 'message_metadata'
    """)).fetchone()
    
    # 결과가 있고 타입이 text가 아닌 경우에만 변경
    if result and result[0].lower() != 'text':
        op.execute(
            """
            ALTER TABLE stockeasy.stockeasy_chat_messages 
            ALTER COLUMN message_metadata TYPE text USING 
            CASE 
                WHEN message_metadata IS NULL THEN NULL
                ELSE message_metadata::text 
            END
            """
        )
