"""fix all datetime fields with timezone and default values

Revision ID: fix_all_datetime_fields
Revises: fix_sessions_last_accessed_at
Create Date: 2025-02-20 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_all_datetime_fields'
down_revision: Union[str, None] = 'fix_sessions_last_accessed_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create or replace the trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # List of all tables that inherit from Base
    tables = [
        'users',
        'sessions',
        'projects',
        'categories',
        'documents',
        'document_chunks',
        'telegram_messages',
        'table_histories'
    ]

    for table in tables:
        # Update timestamp columns to timestamptz and set defaults
        op.execute(f"""
            -- Update any NULL values first
            UPDATE {table} 
            SET created_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP),
                updated_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)
            WHERE created_at IS NULL OR updated_at IS NULL;

            -- Alter columns to use timestamptz and set defaults
            ALTER TABLE {table}
            ALTER COLUMN created_at TYPE timestamptz 
            USING created_at AT TIME ZONE 'UTC',
            ALTER COLUMN created_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP),
            ALTER COLUMN updated_at TYPE timestamptz 
            USING updated_at AT TIME ZONE 'UTC',
            ALTER COLUMN updated_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);

            -- Drop existing trigger if exists
            DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};

            -- Create new trigger
            CREATE TRIGGER update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)

    # Special handling for telegram_messages.message_created_at
    op.execute("""
        ALTER TABLE telegram_messages
        ALTER COLUMN message_created_at TYPE timestamptz 
        USING message_created_at AT TIME ZONE 'UTC';
    """)

    # Special handling for sessions.last_accessed_at
    op.execute("""
        UPDATE sessions 
        SET last_accessed_at = TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP)
        WHERE last_accessed_at IS NULL;

        ALTER TABLE sessions
        ALTER COLUMN last_accessed_at TYPE timestamptz 
        USING last_accessed_at AT TIME ZONE 'UTC',
        ALTER COLUMN last_accessed_at SET DEFAULT TIMEZONE('Asia/Seoul', CURRENT_TIMESTAMP);
    """)


def downgrade() -> None:
    # List of all tables
    tables = [
        'users',
        'sessions',
        'projects',
        'categories',
        'documents',
        'document_chunks',
        'telegram_messages',
        'table_histories'
    ]

    for table in tables:
        # Remove triggers and revert timestamp columns
        op.execute(f"""
            -- Drop trigger
            DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};

            -- Revert columns to timestamp without timezone
            ALTER TABLE {table}
            ALTER COLUMN created_at TYPE timestamp 
            USING created_at AT TIME ZONE 'Asia/Seoul',
            ALTER COLUMN created_at DROP DEFAULT,
            ALTER COLUMN updated_at TYPE timestamp 
            USING updated_at AT TIME ZONE 'Asia/Seoul',
            ALTER COLUMN updated_at DROP DEFAULT;
        """)

    # Special handling for telegram_messages.message_created_at
    op.execute("""
        ALTER TABLE telegram_messages
        ALTER COLUMN message_created_at TYPE timestamp 
        USING message_created_at AT TIME ZONE 'Asia/Seoul';
    """)

    # Special handling for sessions.last_accessed_at
    op.execute("""
        ALTER TABLE sessions
        ALTER COLUMN last_accessed_at TYPE timestamp 
        USING last_accessed_at AT TIME ZONE 'Asia/Seoul',
        ALTER COLUMN last_accessed_at DROP DEFAULT;
    """)

    # Drop the trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();") 