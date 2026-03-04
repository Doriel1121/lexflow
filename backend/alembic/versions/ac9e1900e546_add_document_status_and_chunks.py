"""add_document_status_and_chunks

Revision ID: ac9e1900e546
Revises: 9f038a0f8a9e
Create Date: 2026-03-02 19:54:30.622877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'ac9e1900e546'
down_revision: Union[str, Sequence[str], None] = '9f038a0f8a9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the processing_status enum and add it to documents
    op.execute("CREATE TYPE documentprocessingstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')")
    op.execute("ALTER TABLE documents ADD COLUMN processing_status documentprocessingstatus NOT NULL DEFAULT 'COMPLETED'")

    # 2. Enable pgvector extension securely
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 3. Create the document_chunks table for vector embeddings
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('document_chunks')
    op.execute("ALTER TABLE documents DROP COLUMN processing_status")
    op.execute("DROP TYPE documentprocessingstatus")
