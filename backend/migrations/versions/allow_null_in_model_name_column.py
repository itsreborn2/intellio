"""Allow NULL in model_name column of token_usages table

Revision ID: 4a5bc791d38e
Revises: 45ef99abc123
Create Date: 2025-04-18 15:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a5bc791d38e'
down_revision = '45ef99abc123'
branch_labels = None
depends_on = None


def upgrade():
    """model_name 컬럼을 nullable로 변경"""
    op.alter_column('token_usages', 'model_name',
               existing_type=sa.String(length=100),
               nullable=True)


def downgrade():
    """model_name 컬럼을 non-nullable로 변경"""
    op.alter_column('token_usages', 'model_name',
               existing_type=sa.String(length=100),
               nullable=False) 