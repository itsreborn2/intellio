"""다른_테이블들_change_rate를_price_change_percent로_변경

Revision ID: b2266b27ee43
Revises: 0fb6f716225a
Create Date: 2025-06-04 17:41:06.969976

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2266b27ee43'
down_revision = '0fb6f716225a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SupplyDemand 테이블의 change_rate를 price_change_percent로 변경
    op.alter_column('supply_demand', 'change_rate',
                   new_column_name='price_change_percent',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='등락율(%)',
                   existing_comment='등락율(%)',
                   existing_nullable=True)
    
    # RealtimePrice 테이블의 change_rate를 price_change_percent로 변경
    op.alter_column('realtime_prices', 'change_rate',
                   new_column_name='price_change_percent',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='전일대비 변동률(%)',
                   existing_comment='전일대비 변동률(%)',
                   existing_nullable=True)
    
    # MarketIndex 테이블의 change_rate를 price_change_percent로 변경
    op.alter_column('market_indices', 'change_rate',
                   new_column_name='price_change_percent',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='전일대비 변동률(%)',
                   existing_comment='전일대비 변동률(%)',
                   existing_nullable=True)


def downgrade() -> None:
    # price_change_percent를 change_rate로 복원
    op.alter_column('market_indices', 'price_change_percent',
                   new_column_name='change_rate',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='전일대비 변동률(%)',
                   existing_comment='전일대비 변동률(%)',
                   existing_nullable=True)
    
    op.alter_column('realtime_prices', 'price_change_percent',
                   new_column_name='change_rate',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='전일대비 변동률(%)',
                   existing_comment='전일대비 변동률(%)',
                   existing_nullable=True)
    
    op.alter_column('supply_demand', 'price_change_percent',
                   new_column_name='change_rate',
                   existing_type=sa.Numeric(precision=8, scale=4),
                   comment='등락율(%)',
                   existing_comment='등락율(%)',
                   existing_nullable=True) 