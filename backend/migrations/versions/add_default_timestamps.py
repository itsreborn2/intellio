"""add default timestamps to users table

Revision ID: add_default_timestamps
Revises: 42ec716857fb
Create Date: 2025-02-20 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_default_timestamps'
down_revision: Union[str, None] = '42ec716857fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default values for timestamp columns
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN created_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP),
        ALTER COLUMN updated_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);
        
        -- Create trigger function if not exists
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        -- Create trigger
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Remove default values and trigger
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT;
        
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        DROP FUNCTION IF EXISTS update_updated_at_column();
    """) 