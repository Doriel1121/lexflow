"""add_page_number_to_document_chunks

Revision ID: 69195e739525
Revises: 5d33cbf66774
Create Date: 2026-03-15 10:52:42.188011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69195e739525'
down_revision: Union[str, Sequence[str], None] = '5d33cbf66774'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add page_number column to document_chunks table
    op.add_column('document_chunks', sa.Column('page_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove page_number column from document_chunks table
    op.drop_column('document_chunks', 'page_number')
