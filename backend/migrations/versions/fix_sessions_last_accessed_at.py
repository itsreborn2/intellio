"""fix sessions last_accessed_at default value

Revision ID: fix_sessions_last_accessed_at
Revises: f2a33a18d76c
Create Date: 2025-02-20 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_sessions_last_accessed_at'
down_revision: Union[str, None] = 'f2a33a18d76c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default value for last_accessed_at column
    op.execute("""
        ALTER TABLE sessions 
        ALTER COLUMN last_accessed_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);
        
        -- Update any existing NULL values
        UPDATE sessions 
        SET last_accessed_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)
        WHERE last_accessed_at IS NULL;
    """)


def downgrade() -> None:
    # Remove default value
    op.execute("""
        ALTER TABLE sessions 
        ALTER COLUMN last_accessed_at DROP DEFAULT;
    """) 