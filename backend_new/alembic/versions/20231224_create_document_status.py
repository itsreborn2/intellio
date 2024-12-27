"""create document status enum

Revision ID: 20231224_create_document_status
Revises: 595d4c6dfcc1
Create Date: 2023-12-24 01:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20231224_create_document_status'
down_revision: Union[str, None] = '595d4c6dfcc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 기존 enum 타입이 있다면 삭제
    op.execute('DROP TYPE IF EXISTS document_status CASCADE')
    
    # 2. documents 테이블 생성
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('file_type', sa.String(100), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # VARCHAR로 변경
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('embedding_ids', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    # 1. documents 테이블 삭제
    op.drop_table('documents')
