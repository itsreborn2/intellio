"""add category model

Revision ID: ea5691a8767e
Revises: 7bc6492116ce
Create Date: 2024-12-25 18:20:24.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea5691a8767e'
down_revision: Union[str, None] = '7bc6492116ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 먼저 기존 외래 키 제약 조건을 제거
    op.drop_constraint('projects_category_id_fkey', 'projects', type_='foreignkey')
    
    # categories 테이블 생성
    op.create_table('categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # project_categories 테이블 재생성
    op.drop_table('project_categories')
    op.create_table('project_categories',
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id', 'category_id')
    )

    # projects 테이블 변경
    op.add_column('projects', sa.Column('is_temporary', sa.Boolean(), nullable=True))
    op.alter_column('projects', 'description',
               existing_type=sa.VARCHAR(length=1000),
               type_=sa.Text(),
               existing_nullable=True)
    op.drop_column('projects', 'category_id')
    op.drop_column('projects', 'is_permanent')
    op.drop_column('projects', 'last_accessed_at')

    # users 테이블에 name 컬럼 추가
    op.add_column('users', sa.Column('name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # users 테이블에서 name 컬럼 제거
    op.drop_column('users', 'name')

    # 테이블 삭제
    op.drop_table('project_categories')
    op.drop_table('categories')
    
    # projects 테이블 복원
    op.add_column('projects', sa.Column('last_accessed_at', sa.DateTime(), nullable=True))
    op.add_column('projects', sa.Column('is_permanent', sa.Boolean(), nullable=True))
    op.add_column('projects', sa.Column('category_id', sa.UUID(), nullable=True))
    op.alter_column('projects', 'description',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=1000),
               existing_nullable=True)
    op.drop_column('projects', 'is_temporary')
