"""Session Table의 session id 삭제. 그냥 id 이용

Revision ID: 05157a1b9591
Revises: a66f67c23883
Create Date: 2025-02-04 20:16:28.500222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05157a1b9591'
down_revision: Union[str, None] = 'a66f67c23883'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('projects', 'order')
    op.drop_index('ix_sessions_session_id', table_name='sessions')
    op.drop_column('sessions', 'session_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sessions', sa.Column('session_id', sa.VARCHAR(length=100), autoincrement=False, nullable=False))
    op.create_index('ix_sessions_session_id', 'sessions', ['session_id'], unique=True)
    op.add_column('projects', sa.Column('order', sa.INTEGER(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
