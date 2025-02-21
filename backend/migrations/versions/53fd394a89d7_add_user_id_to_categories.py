"""add user_id to categories

Revision ID: 53fd394a89d7
Revises: 0fcb944d8867
Create Date: 2025-01-06 14:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '53fd394a89d7'
down_revision = '0fcb944d8867'  # 현재 head로 수정
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. user_id 컬럼 추가
    op.add_column('categories', sa.Column('user_id', UUID(as_uuid=True), nullable=True))
    
    # 2. 기존 레코드가 있다면 임시로 NULL 허용
    
    # 3. NOT NULL 제약조건 추가
    op.alter_column('categories', 'user_id',
                    existing_type=UUID(as_uuid=True),
                    nullable=False)


def downgrade() -> None:
    # user_id 컬럼 제거
    op.drop_column('categories', 'user_id') 