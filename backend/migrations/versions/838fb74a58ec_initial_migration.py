"""initial_migration

Revision ID: 838fb74a58ec
Revises: 
Create Date: 2024-12-23 21:02:36.304233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '838fb74a58ec'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create project_categories table first
    op.create_table('project_categories',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create users table if not exists
    op.create_table('users',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_anonymous', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('analysis_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create enum types using direct SQL execution
    connection = op.get_bind()
    connection.execute(sa.text('DROP TYPE IF EXISTS retentionperiod CASCADE'))
    connection.execute(sa.text('DROP TYPE IF EXISTS document_status CASCADE'))
    connection.execute(sa.text("CREATE TYPE retentionperiod AS ENUM ('FIVE_DAYS', 'PERMANENT')"))
    connection.execute(sa.text("CREATE TYPE document_status AS ENUM ('REGISTERED', 'PROCESSING', 'COMPLETED', 'FAILED')"))

    # Create base projects table
    op.create_table('projects',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('category_id', postgresql.UUID(), nullable=True),
        sa.Column('is_permanent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('retention_period', postgresql.ENUM('FIVE_DAYS', 'PERMANENT', name='retentionperiod', create_type=False), server_default='FIVE_DAYS', nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['project_categories.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create documents table
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False, server_default=sa.text("'Untitled'")),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('status', postgresql.ENUM('REGISTERED', 'PROCESSING', 'COMPLETED', 'FAILED', name='document_status', create_type=False), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('embedding_ids', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table('documents')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('project_categories')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS document_status CASCADE')
    op.execute('DROP TYPE IF EXISTS retentionperiod CASCADE')
