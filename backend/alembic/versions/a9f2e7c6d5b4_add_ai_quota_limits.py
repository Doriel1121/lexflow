"""add ai quota limits

Revision ID: a9f2e7c6d5b4
Revises: f2a1b3c4d5e6
Create Date: 2026-07-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9f2e7c6d5b4"
down_revision: Union[str, None] = "f2a1b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("ai_daily_call_limit", sa.Integer(), nullable=True, server_default="1000"),
    )
    op.add_column(
        "organizations",
        sa.Column("ai_monthly_drafting_limit", sa.Integer(), nullable=True, server_default="100"),
    )
    op.add_column(
        "organizations",
        sa.Column("ai_monthly_token_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "ai_monthly_token_limit")
    op.drop_column("organizations", "ai_monthly_drafting_limit")
    op.drop_column("organizations", "ai_daily_call_limit")
