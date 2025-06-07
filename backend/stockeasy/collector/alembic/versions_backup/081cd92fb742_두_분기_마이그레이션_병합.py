"""두_분기_마이그레이션_병합

Revision ID: 081cd92fb742
Revises: 08d15a142dac, fix_price_change_percent_precision
Create Date: 2025-06-06 16:15:58.270807

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '081cd92fb742'
down_revision = ('08d15a142dac', 'fix_price_change_percent_precision')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 