"""add_period_data_fields_to_summary_financial_data

Revision ID: ac9c2382b96f
Revises: fdcd55a3281a
Create Date: 2025-04-20 22:47:45.270241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ac9c2382b96f'
down_revision: Union[str, None] = 'fdcd55a3281a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 새 필드만 추가
    op.add_column('summary_financial_data', sa.Column('cumulative_value', sa.Numeric(precision=30, scale=2), nullable=True), schema='stockeasy')
    op.add_column('summary_financial_data', sa.Column('period_value', sa.Numeric(precision=30, scale=2), nullable=True), schema='stockeasy')
    op.add_column('summary_financial_data', sa.Column('is_cumulative', sa.Boolean(), nullable=True), schema='stockeasy')
    op.add_column('summary_financial_data', sa.Column('statement_type', sa.String(length=30), nullable=True), schema='stockeasy')


def downgrade() -> None:
    # 필드 제거
    op.drop_column('summary_financial_data', 'statement_type', schema='stockeasy')
    op.drop_column('summary_financial_data', 'is_cumulative', schema='stockeasy')
    op.drop_column('summary_financial_data', 'period_value', schema='stockeasy')
    op.drop_column('summary_financial_data', 'cumulative_value', schema='stockeasy')
