"""add name to users

Revision ID: 679295943d52
Revises: ea5691a8767e
Create Date: 2024-12-25 18:25:44.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '679295943d52'
down_revision: Union[str, None] = 'ea5691a8767e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users 테이블에 name 컬럼 추가
    op.add_column('users', sa.Column('name', sa.String(length=100), nullable=True))
    # 기존 사용자의 name을 email에서 추출하여 설정
    op.execute("UPDATE users SET name = split_part(email, '@', 1) WHERE name IS NULL")


def downgrade() -> None:
    # users 테이블에서 name 컬럼 제거
    op.drop_column('users', 'name')
