"""add commute_favorites table

7f3a9c2e5b1d 위에 이어서 체이닝한다.

Revision ID: 2a6d8e1f4c93
Revises: 7f3a9c2e5b1d
Create Date: 2026-07-20 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2a6d8e1f4c93'
down_revision: Union[str, None] = '7f3a9c2e5b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'commute_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=30), nullable=False),
        sa.Column('origin_address', sa.String(length=255), nullable=False),
        sa.Column('origin_lat', sa.Float(), nullable=False),
        sa.Column('origin_lng', sa.Float(), nullable=False),
        sa.Column('destination_address', sa.String(length=255), nullable=False),
        sa.Column('destination_lat', sa.Float(), nullable=False),
        sa.Column('destination_lng', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('commute_favorites')
