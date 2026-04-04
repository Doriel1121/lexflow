"""Add missing system_metrics_daily and tenant_cohorts tables

Revision ID: 003_add_system_analytics_tables
Revises: 002_fix_system_events_schema
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '003_add_system_analytics_tables'
down_revision: Union[str, Sequence[str], None] = '002_fix_system_events_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_metrics_daily table
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics_daily (
            id INTEGER NOT NULL PRIMARY KEY,
            metric_date DATE NOT NULL UNIQUE,
            total_orgs INTEGER DEFAULT 0,
            active_orgs INTEGER DEFAULT 0,
            inactive_orgs INTEGER DEFAULT 0,
            new_orgs_today INTEGER DEFAULT 0,
            total_users INTEGER DEFAULT 0,
            active_users_today INTEGER DEFAULT 0,
            new_users_today INTEGER DEFAULT 0,
            total_documents INTEGER DEFAULT 0,
            new_documents_today INTEGER DEFAULT 0,
            total_cases INTEGER DEFAULT 0,
            new_cases_today INTEGER DEFAULT 0,
            ai_calls_today INTEGER DEFAULT 0,
            api_requests_today INTEGER DEFAULT 0,
            api_errors_today INTEGER DEFAULT 0,
            avg_latency_ms FLOAT DEFAULT 0.0,
            p95_latency_ms FLOAT DEFAULT 0.0,
            feature_usage TEXT,
            computed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    op.execute("CREATE INDEX IF NOT EXISTS idx_metrics_daily_date ON system_metrics_daily (metric_date)")
    
    # Create tenant_cohorts table
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_cohorts (
            id INTEGER NOT NULL PRIMARY KEY,
            cohort_month DATE NOT NULL UNIQUE,
            new_tenants INTEGER DEFAULT 0,
            churned_tenants INTEGER DEFAULT 0,
            active_tenants INTEGER DEFAULT 0
        )
    """)
    
    op.execute("CREATE INDEX IF NOT EXISTS idx_cohorts_month ON tenant_cohorts (cohort_month)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_cohorts CASCADE")
    op.execute("DROP TABLE IF EXISTS system_metrics_daily CASCADE")
