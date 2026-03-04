"""add category to tags

Revision ID: 05da289d0c85
Revises: 5d98961b38f5
Create Date: 2026-02-28 20:37:06.604985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05da289d0c85'
down_revision: Union[str, Sequence[str], None] = '5d98961b38f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tags', sa.Column('category', sa.String(), nullable=True))
    op.create_index(op.f('ix_tags_category'), 'tags', ['category'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tags_category'), table_name='tags')
    op.drop_column('tags', 'category')
