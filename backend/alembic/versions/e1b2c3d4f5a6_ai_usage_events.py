"""ai usage events

Revision ID: e1b2c3d4f5a6
Revises: d4e8c1a9f2b0
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1b2c3d4f5a6"
down_revision: Union[str, Sequence[str], None] = "d4e8c1a9f2b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_chars", sa.Integer(), nullable=True),
        sa.Column("output_chars", sa.Integer(), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_usage_events_id"), "ai_usage_events", ["id"], unique=False)
    op.create_index(op.f("ix_ai_usage_events_organization_id"), "ai_usage_events", ["organization_id"], unique=False)
    op.create_index(op.f("ix_ai_usage_events_task_type"), "ai_usage_events", ["task_type"], unique=False)
    op.create_index(op.f("ix_ai_usage_events_provider"), "ai_usage_events", ["provider"], unique=False)
    op.create_index(op.f("ix_ai_usage_events_status"), "ai_usage_events", ["status"], unique=False)
    op.create_index(op.f("ix_ai_usage_events_created_at"), "ai_usage_events", ["created_at"], unique=False)
    op.create_index("ix_ai_usage_events_created_task", "ai_usage_events", ["created_at", "task_type"], unique=False)
    op.create_index("ix_ai_usage_events_org_created", "ai_usage_events", ["organization_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_org_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created_task", table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_created_at"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_status"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_provider"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_task_type"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_organization_id"), table_name="ai_usage_events")
    op.drop_index(op.f("ix_ai_usage_events_id"), table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
