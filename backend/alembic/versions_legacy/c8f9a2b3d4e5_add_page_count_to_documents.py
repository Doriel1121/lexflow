"""add_page_count_to_documents

Revision ID: c8f9a2b3d4e5
Revises: b76aa1711216
Create Date: 2026-02-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f9a2b3d4e5'
down_revision: Union[str, Sequence[str], None] = 'b76aa1711216'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add page_count column to documents table."""
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove page_count column from documents table."""
    op.drop_column('documents', 'page_count')
