"""system analytics tables

Revision ID: f2a1b3c4d5e6
Revises: e1b2c3d4f5a6
Create Date: 2026-07-07

Creates the three tables required by the admin dashboard:
  - system_events        : raw anonymised event stream
  - system_metrics_daily : pre-aggregated daily snapshots
  - tenant_cohorts       : monthly growth cohorts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a1b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e1b2c3d4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── system_events ────────────────────────────────────────────────────────
    op.create_table(
        "system_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=True),
        sa.Column("org_bucket", sa.Integer(), nullable=True),
        sa.Column("user_bucket", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sysevt_type_time", "system_events", ["event_type", "occurred_at"])
    op.create_index("idx_sysevt_feature_time", "system_events", ["feature", "occurred_at"])
    op.create_index(op.f("ix_system_events_event_type"), "system_events", ["event_type"])
    op.create_index(op.f("ix_system_events_feature"), "system_events", ["feature"])
    op.create_index(op.f("ix_system_events_occurred_at"), "system_events", ["occurred_at"])

    # ── system_metrics_daily ─────────────────────────────────────────────────
    op.create_table(
        "system_metrics_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("total_orgs", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("active_orgs", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("inactive_orgs", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("new_orgs_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_users", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("active_users_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("new_users_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_documents", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("new_documents_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_cases", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("new_cases_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("ai_calls_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("api_requests_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("api_errors_today", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("feature_usage", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_date"),
    )
    op.create_index(op.f("ix_system_metrics_daily_metric_date"), "system_metrics_daily", ["metric_date"])

    # ── tenant_cohorts ───────────────────────────────────────────────────────
    op.create_table(
        "tenant_cohorts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cohort_month", sa.Date(), nullable=False),
        sa.Column("new_tenants", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("churned_tenants", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("active_tenants", sa.Integer(), nullable=True, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_month"),
    )
    op.create_index(op.f("ix_tenant_cohorts_cohort_month"), "tenant_cohorts", ["cohort_month"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tenant_cohorts_cohort_month"), table_name="tenant_cohorts")
    op.drop_table("tenant_cohorts")

    op.drop_index(op.f("ix_system_metrics_daily_metric_date"), table_name="system_metrics_daily")
    op.drop_table("system_metrics_daily")

    op.drop_index(op.f("ix_system_events_occurred_at"), table_name="system_events")
    op.drop_index(op.f("ix_system_events_feature"), table_name="system_events")
    op.drop_index(op.f("ix_system_events_event_type"), table_name="system_events")
    op.drop_index("idx_sysevt_feature_time", table_name="system_events")
    op.drop_index("idx_sysevt_type_time", table_name="system_events")
    op.drop_table("system_events")
