"""add name to users

Revision ID: 679295943d52
Revises: ea5691a8767e
Create Date: 2024-12-25 18:25:44.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

# revision identifiers, used by Alembic.
revision: str = '679295943d52'
down_revision: Union[str, None] = 'ea5691a8767e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reflect the existing table
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    
    # Check if the 'name' column already exists
    columns = [column['name'] for column in inspector.get_columns('users')]
    if 'name' not in columns:
        op.add_column('users', sa.Column('name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # users 테이블에서 name 컬럼 제거
    op.drop_column('users', 'name')
