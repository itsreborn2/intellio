"""create stockeasy chat tables

Revision ID: 618bd77ea524
Revises: 94f4a7823be1
Create Date: 2025-04-04 22:20:18.103388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '618bd77ea524'
down_revision: Union[str, None] = '94f4a7823be1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 스키마 존재 여부 확인 및 생성
    conn = op.get_bind()
    inspector = inspect(conn)
    schemas = inspector.get_schema_names()
    
    if 'stockeasy' not in schemas:
        op.execute('CREATE SCHEMA IF NOT EXISTS stockeasy')
        
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('stockeasy_chat_sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False, comment='채팅 세션 ID'),
    sa.Column('user_id', sa.UUID(), nullable=False, comment='사용자 ID'),
    sa.Column('title', sa.String(length=255), server_default='새 채팅', nullable=False, comment='채팅 세션 제목'),
    sa.Column('stock_code', sa.String(length=20), nullable=True, comment='종목 코드'),
    sa.Column('stock_name', sa.String(length=100), nullable=True, comment='종목명'),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False, comment='활성화 여부'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"), nullable=False, comment='생성 시간 (Asia/Seoul)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"), nullable=False, comment='수정 시간 (Asia/Seoul)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='stockeasy'
    )
    op.create_index(op.f('ix_stockeasy_stockeasy_chat_sessions_stock_code'), 'stockeasy_chat_sessions', ['stock_code'], unique=False, schema='stockeasy')
    op.create_index(op.f('ix_stockeasy_stockeasy_chat_sessions_stock_name'), 'stockeasy_chat_sessions', ['stock_name'], unique=False, schema='stockeasy')
    op.create_index(op.f('ix_stockeasy_stockeasy_chat_sessions_user_id'), 'stockeasy_chat_sessions', ['user_id'], unique=False, schema='stockeasy')
    op.create_table('stockeasy_chat_messages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False, comment='메시지 ID'),
    sa.Column('session_id', sa.UUID(), nullable=False, comment='채팅 세션 ID'),
    sa.Column('role', sa.String(length=20), nullable=False, comment='메시지 역할 (user, assistant, system)'),
    sa.Column('content', sa.Text(), nullable=False, comment='메시지 내용'),
    sa.Column('message_metadata', sa.Text(), nullable=True, comment='메시지 메타데이터 (JSON 형태)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"), nullable=False, comment='생성 시간 (Asia/Seoul)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)"), nullable=False, comment='수정 시간 (Asia/Seoul)'),
    sa.ForeignKeyConstraint(['session_id'], ['stockeasy.stockeasy_chat_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='stockeasy'
    )
    op.create_index('ix_stockeasy_chat_messages_session_id_created_at', 'stockeasy_chat_messages', ['session_id', 'created_at'], unique=False, schema='stockeasy')
    op.create_index(op.f('ix_stockeasy_stockeasy_chat_messages_session_id'), 'stockeasy_chat_messages', ['session_id'], unique=False, schema='stockeasy')
    op.alter_column('telegram_messages', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment='생성 시간 (Asia/Seoul)',
               existing_nullable=False,
               existing_server_default=sa.text("timezone('Asia/Seoul'::text, CURRENT_TIMESTAMP)"))
    op.alter_column('telegram_messages', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment='수정 시간 (Asia/Seoul)',
               existing_nullable=False,
               existing_server_default=sa.text("timezone('Asia/Seoul'::text, CURRENT_TIMESTAMP)"))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('telegram_messages', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment='수정 시간 (Asia/Seoul)',
               existing_nullable=False,
               existing_server_default=sa.text("timezone('Asia/Seoul'::text, CURRENT_TIMESTAMP)"))
    op.alter_column('telegram_messages', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment='생성 시간 (Asia/Seoul)',
               existing_nullable=False,
               existing_server_default=sa.text("timezone('Asia/Seoul'::text, CURRENT_TIMESTAMP)"))
    op.drop_index(op.f('ix_stockeasy_stockeasy_chat_messages_session_id'), table_name='stockeasy_chat_messages', schema='stockeasy')
    op.drop_index('ix_stockeasy_chat_messages_session_id_created_at', table_name='stockeasy_chat_messages', schema='stockeasy')
    op.drop_table('stockeasy_chat_messages', schema='stockeasy')
    op.drop_index(op.f('ix_stockeasy_stockeasy_chat_sessions_user_id'), table_name='stockeasy_chat_sessions', schema='stockeasy')
    op.drop_index(op.f('ix_stockeasy_stockeasy_chat_sessions_stock_name'), table_name='stockeasy_chat_sessions', schema='stockeasy')
    op.drop_index(op.f('ix_stockeasy_stockeasy_chat_sessions_stock_code'), table_name='stockeasy_chat_sessions', schema='stockeasy')
    op.drop_table('stockeasy_chat_sessions', schema='stockeasy')
    
    # 스키마 내 모든 테이블이 삭제된 후 스키마도 삭제
    # 주의: 다른 테이블이 stockeasy 스키마에 있는 경우 오류 발생 가능
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names(schema='stockeasy')
    
    if not tables:
        op.execute('DROP SCHEMA IF EXISTS stockeasy')
    # ### end Alembic commands ###
