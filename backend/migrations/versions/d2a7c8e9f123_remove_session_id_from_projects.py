"""remove session_id from projects

Revision ID: d2a7c8e9f123
Revises: e8c45eb57e34
Create Date: 2025-01-18 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2a7c8e9f123'
down_revision = 'e8c45eb57e34'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 외래 키 제약조건이 있다면 먼저 제거
    try:
        op.drop_constraint('projects_session_id_fkey', 'projects', type_='foreignkey')
    except:
        pass  # 제약조건이 없는 경우 무시
    
    # session_id 컬럼 제거
    op.drop_column('projects', 'session_id')


def downgrade() -> None:
    # session_id 컬럼 다시 추가
    op.add_column('projects',
        sa.Column('session_id', sa.String(length=255), nullable=True)
    )
    
    # 외래 키 제약조건 다시 추가
    op.create_foreign_key(
        'projects_session_id_fkey',
        'projects', 'sessions',
        ['session_id'], ['session_id']
    )
