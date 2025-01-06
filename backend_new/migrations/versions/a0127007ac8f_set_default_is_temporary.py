"""set default is_temporary

Revision ID: a0127007ac8f
Revises: ea5691a8767e
Create Date: 2024-12-25 18:30:05.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0127007ac8f'
down_revision: Union[str, None] = 'ea5691a8767e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 NULL 값을 False로 업데이트
    op.execute("UPDATE projects SET is_temporary = FALSE WHERE is_temporary IS NULL")
    
    # is_temporary 컬럼에 NOT NULL 제약 조건과 기본값 추가
    op.alter_column('projects', 'is_temporary',
                    existing_type=sa.BOOLEAN(),
                    nullable=False,
                    server_default=sa.text('false'))
    
    # created_at과 updated_at에 기본값 설정
    op.alter_column('projects', 'created_at',
                    existing_type=sa.DateTime(),
                    server_default=sa.text('now()'),
                    nullable=False)
    op.alter_column('projects', 'updated_at',
                    existing_type=sa.DateTime(),
                    server_default=sa.text('now()'),
                    nullable=False)


def downgrade() -> None:
    # 제약 조건 제거
    op.alter_column('projects', 'is_temporary',
                    existing_type=sa.BOOLEAN(),
                    nullable=True,
                    server_default=None)
    op.alter_column('projects', 'created_at',
                    existing_type=sa.DateTime(),
                    server_default=None,
                    nullable=True)
    op.alter_column('projects', 'updated_at',
                    existing_type=sa.DateTime(),
                    server_default=None,
                    nullable=True)
