"""update_datetime_fields_to_seoul_timezone_3

Revision ID: 9a1ebe1109fd
Revises: 735d45ecd5a2
Create Date: 2025-02-20 16:56:06.914575

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '9a1ebe1109fd'
down_revision: Union[str, None] = '735d45ecd5a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update created_at and updated_at columns for all tables that inherit from Base
    for table in ['documents', 'document_chunks', 'projects', 'categories', 'users', 'sessions']:
        # First convert existing timestamps to timestamptz with Asia/Seoul timezone
        op.execute(f"""
            ALTER TABLE {table} 
            ALTER COLUMN created_at TYPE timestamptz 
            USING created_at AT TIME ZONE 'UTC';
            
            ALTER TABLE {table} 
            ALTER COLUMN updated_at TYPE timestamptz 
            USING updated_at AT TIME ZONE 'UTC';
        """)
        
        # Then update the default values
        op.execute(f"""
            ALTER TABLE {table} 
            ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
            ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul';
            
            CREATE OR REPLACE TRIGGER update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION trigger_set_timestamp_with_timezone();
        """)


def downgrade() -> None:
    # Revert changes
    for table in ['documents', 'document_chunks', 'projects', 'categories', 'users', 'sessions']:
        # Drop the trigger first
        op.execute(f"""
            DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
        """)
        
        # Then convert timestamptz back to timestamp
        op.execute(f"""
            ALTER TABLE {table} 
            ALTER COLUMN created_at TYPE timestamp 
            USING created_at AT TIME ZONE 'Asia/Seoul',
            ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
            ALTER COLUMN updated_at TYPE timestamp 
            USING updated_at AT TIME ZONE 'Asia/Seoul',
            ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
        """)

# Create trigger function for timestamptz
def create_trigger_function() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_set_timestamp_with_timezone()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul';
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

# Drop trigger function
def drop_trigger_function() -> None:
    op.execute("DROP FUNCTION IF EXISTS trigger_set_timestamp_with_timezone();")

# Add trigger function creation/deletion to upgrade/downgrade
def upgrade() -> None:
    create_trigger_function()
    # Rest of the upgrade code...

def downgrade() -> None:
    # Rest of the downgrade code...
    drop_trigger_function()
