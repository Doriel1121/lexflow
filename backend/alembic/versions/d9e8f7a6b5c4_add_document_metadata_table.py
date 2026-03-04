"""add_document_metadata_table

Revision ID: d9e8f7a6b5c4
Revises: c8f9a2b3d4e5
Create Date: 2026-02-08 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd9e8f7a6b5c4'
down_revision: Union[str, Sequence[str], None] = 'c8f9a2b3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_metadata table."""
    op.create_table(
        'document_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('dates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('entities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('amounts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('case_numbers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )
    op.create_index(op.f('ix_document_metadata_id'), 'document_metadata', ['id'], unique=False)


def downgrade() -> None:
    """Drop document_metadata table."""
    op.drop_index(op.f('ix_document_metadata_id'), table_name='document_metadata')
    op.drop_table('document_metadata')
