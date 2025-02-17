"""add project session fk

Revision ID: 595d4c6dfcc1
Revises: 2689a9157224
Create Date: 2023-12-24 00:54:16.000000

"""
from typing import Sequence, Union
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '595d4c6dfcc1'
down_revision = '2689a9157224'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 기존 외래 키 제거
    op.drop_constraint('projects_session_id_fkey', 'projects', type_='foreignkey')
    
    # 2. retention_period 컬럼 제거
    op.drop_column('projects', 'retention_period')
    
    # 3. session_id 컬럼 타입 변경
    op.alter_column('projects', 'session_id',
        existing_type=postgresql.UUID(),
        type_=sa.String(length=255),
        existing_nullable=False)
    
    # 4. 기존 프로젝트의 세션 데이터 마이그레이션
    conn = op.get_bind()
    
    # 4.1. 프로젝트 데이터 조회
    projects = conn.execute(
        sa.text('SELECT id, session_id, user_id FROM projects')
    ).fetchall()
    
    # 4.2. 세션 테이블에 데이터 삽입
    for project in projects:
        # 세션이 이미 있는지 확인
        session = conn.execute(
            sa.text('SELECT id FROM sessions WHERE session_id = :session_id'),
            {'session_id': project.session_id}
        ).first()
        
        if not session:
            # 현재 시간을 모든 타임스탬프에 사용
            now = datetime.utcnow()
            # 세션 생성
            conn.execute(
                sa.text('''
                    INSERT INTO sessions (id, session_id, user_id, is_anonymous, created_at, updated_at, last_accessed_at)
                    VALUES (:id, :session_id, :user_id, :is_anonymous, :created_at, :updated_at, :last_accessed_at)
                '''),
                {
                    'id': str(uuid.uuid4()),
                    'session_id': project.session_id,
                    'user_id': project.user_id,
                    'is_anonymous': project.user_id is None,
                    'created_at': now,
                    'updated_at': now,
                    'last_accessed_at': now
                }
            )
    
    # 5. 새로운 외래 키 추가
    op.create_foreign_key(
        'projects_session_id_fkey', 'projects', 'sessions',
        ['session_id'], ['session_id']
    )


def downgrade() -> None:
    # 1. 새로운 외래 키 제거
    op.drop_constraint('projects_session_id_fkey', 'projects', type_='foreignkey')
    
    # 2. session_id 컬럼 타입 복원
    op.alter_column('projects', 'session_id',
        existing_type=sa.String(length=255),
        type_=postgresql.UUID(),
        existing_nullable=False)
    
    # 3. retention_period 컬럼 복원
    op.add_column('projects', sa.Column('retention_period', sa.String(length=50), nullable=False))
    
    # 4. 기존 외래 키 복원
    op.create_foreign_key(
        'projects_session_id_fkey', 'projects', 'sessions',
        ['session_id'], ['id']
    )
