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
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentprocessingstatus') THEN
                CREATE TYPE documentprocessingstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
            END IF;
        END $$;
    """)
    op.execute("""
        ALTER TABLE documents
        ADD COLUMN IF NOT EXISTS processing_status documentprocessingstatus NOT NULL DEFAULT 'COMPLETED'
    """)

    # 2. Enable pgvector extension securely
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 3. Create the document_chunks table for vector embeddings
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL NOT NULL,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            embedding vector(768),
            PRIMARY KEY (id),
            FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON document_chunks (document_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_id ON document_chunks (id)"
    )


def downgrade() -> None:
    op.drop_table('document_chunks')
    op.execute("ALTER TABLE documents DROP COLUMN processing_status")
    op.execute("DROP TYPE documentprocessingstatus")
