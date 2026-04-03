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
    # Use IF NOT EXISTS to make the migration idempotent for environments where the table
    # may have been created manually or by a previous run.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_metadata (
            id SERIAL NOT NULL,
            document_id INTEGER NOT NULL,
            dates JSONB,
            entities JSONB,
            amounts JSONB,
            case_numbers JSONB,
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE,
            PRIMARY KEY (id),
            UNIQUE (document_id),
            FOREIGN KEY(document_id) REFERENCES documents (id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_metadata_id ON document_metadata (id)"
    )


def downgrade() -> None:
    """Drop document_metadata table."""
    op.drop_index(op.f('ix_document_metadata_id'), table_name='document_metadata')
    op.drop_table('document_metadata')
