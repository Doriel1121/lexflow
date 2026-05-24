"""document ai_health and embedding_failed_count

Revision ID: a8f3c1d2e4b5
Revises: 7e2a2f9a6b3a
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8f3c1d2e4b5"
down_revision: Union[str, Sequence[str], None] = "7e2a2f9a6b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("embedding_failed_count", sa.Integer(), server_default="0", nullable=True),
    )
    op.add_column("documents", sa.Column("ai_health", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "ai_health")
    op.drop_column("documents", "embedding_failed_count")
