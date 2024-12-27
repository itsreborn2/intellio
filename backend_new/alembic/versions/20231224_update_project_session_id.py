"""update project session id

Revision ID: 20231224_update_project_session_id
Revises: 2689a9157224
Create Date: 2023-12-24 00:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20231224_update_project_session_id'
down_revision: Union[str, None] = '2689a9157224'  # 현재 head revision
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 임시 컬럼 생성
    op.add_column('projects', sa.Column('session_id_new', sa.String(36), nullable=True))
    
    # 2. 데이터 마이그레이션
    op.execute("""
        UPDATE projects p
        SET session_id_new = (
            SELECT session_id
            FROM sessions s
            WHERE s.id = p.session_id::uuid
        )
    """)
    
    # 3. 기존 컬럼 삭제
    op.drop_column('projects', 'session_id')
    
    # 4. 임시 컬럼 이름 변경
    op.alter_column('projects', 'session_id_new',
                    new_column_name='session_id',
                    nullable=False)


def downgrade() -> None:
    # 1. 임시 컬럼 생성
    op.add_column('projects', sa.Column('session_id_old', postgresql.UUID(), nullable=True))
    
    # 2. 데이터 마이그레이션
    op.execute("""
        UPDATE projects p
        SET session_id_old = (
            SELECT id
            FROM sessions s
            WHERE s.session_id = p.session_id
        )
    """)
    
    # 3. 기존 컬럼 삭제
    op.drop_column('projects', 'session_id')
    
    # 4. 임시 컬럼 이름 변경
    op.alter_column('projects', 'session_id_old',
                    new_column_name='session_id',
                    nullable=False)
    
    # 5. 외래 키 제약 조건 추가
    op.create_foreign_key(
        'projects_session_id_fkey',
        'projects', 'sessions',
        ['session_id'], ['id']
    )
