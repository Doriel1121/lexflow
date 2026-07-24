"""add document scale indexes

Revision ID: b1c2d3e4f5a7
Revises: a9f2e7c6d5b4
Create Date: 2026-07-22 00:00:00.000000

Adds indexes for the first scale-readiness phase:
- fast tenant/user/case document listing by newest documents
- efficient chunk ordering/access per document
- trigram support for current ILIKE filename/classification/content search
- pgvector HNSW cosine index for Ask AI retrieval
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b1c2d3e4f5a7"
down_revision: Union[str, None] = "a9f2e7c6d5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_org_created_id "
        "ON documents (organization_id, created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_user_created_id "
        "ON documents (uploaded_by_user_id, created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_case_created_id "
        "ON documents (case_id, created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_doc_chunk "
        "ON document_chunks (document_id, chunk_index)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_filename_trgm "
        "ON documents USING gin (filename gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_classification_trgm "
        "ON documents USING gin (classification gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_content_trgm "
        "ON documents USING gin (content gin_trgm_ops) "
        "WHERE content IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_text_trgm "
        "ON document_chunks USING gin (text_content gin_trgm_ops)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw_cosine "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw_cosine")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_classification_trgm")
    op.execute("DROP INDEX IF EXISTS ix_documents_filename_trgm")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_doc_chunk")
    op.execute("DROP INDEX IF EXISTS ix_documents_case_created_id")
    op.execute("DROP INDEX IF EXISTS ix_documents_user_created_id")
    op.execute("DROP INDEX IF EXISTS ix_documents_org_created_id")