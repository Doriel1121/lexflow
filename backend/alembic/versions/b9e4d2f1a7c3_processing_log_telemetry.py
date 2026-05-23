"""processing log telemetry columns

Revision ID: b9e4d2f1a7c3
Revises: a8f3c1d2e4b5
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b9e4d2f1a7c3"
down_revision: Union[str, Sequence[str], None] = "a8f3c1d2e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_processing_logs",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_processing_logs",
        sa.Column("event_type", sa.String(length=32), server_default="error", nullable=False),
    )
    op.add_column(
        "document_processing_logs",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_processing_logs",
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_processing_logs_organization_id",
        "document_processing_logs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_processing_logs_organization_id",
        "document_processing_logs",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_processing_logs_organization_id", "document_processing_logs")
    op.drop_constraint("fk_processing_logs_organization_id", "document_processing_logs", type_="foreignkey")
    op.drop_column("document_processing_logs", "metadata_json")
    op.drop_column("document_processing_logs", "duration_ms")
    op.drop_column("document_processing_logs", "event_type")
    op.drop_column("document_processing_logs", "organization_id")
