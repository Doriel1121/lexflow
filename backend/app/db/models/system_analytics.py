"""
system_analytics.py
====================
Analytics models for the System Admin dashboard.

These tables store ONLY aggregated, anonymized system-level data.
They NEVER contain org names, org IDs, user emails, or any tenant-identifiable fields.

Design principles:
  - system_events: raw event stream (org_bucket/user_bucket are hashed, not real IDs)
  - system_metrics_daily: pre-aggregated daily snapshot (queried by dashboard)
  - tenant_cohorts: monthly growth tracking (counts only, no identity)
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, BigInteger, Float, String, Date, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON  # fallback for dev SQLite
from app.db.base import Base
import sqlalchemy as sa


def _json_col():
    """Return JSONB for Postgres, JSON for SQLite (dev)."""
    from app.core.config import settings
    if "postgresql" in settings.DATABASE_URL:
        return JSONB
    return JSON


class SystemEvent(Base):
    """
    Raw system event stream.

    Rules:
    - org_bucket: anonymized (hash(org_id) % 10000) — NOT a real org ID
    - user_bucket: anonymized (hash(user_id) % 10000) — NOT a real user ID
    - metadata: must NEVER contain org names, emails, or doc titles
    """
    __tablename__ = "system_events"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type  = Column(String(100), nullable=False, index=True)
    # e.g. 'document.created', 'ai.call', 'user.login', 'case.opened'

    feature     = Column(String(100), nullable=True, index=True)
    # e.g. 'document_upload', 'ai_chat', 'risk_analysis', 'deadline_tracker'

    # Anonymized bucket IDs — safe for system admin to see
    org_bucket  = Column(Integer, nullable=True)   # hash(org_id) % 10000
    user_bucket = Column(Integer, nullable=True)   # hash(user_id) % 10000

    status      = Column(String(20), nullable=True)   # 'success' | 'error' | 'timeout'
    latency_ms  = Column(Integer, nullable=True)

    # Must contain NO identifying data
    extra       = Column(JSONB if False else sa.Text, nullable=True)
    # Stored as JSON string for SQLite compat; use JSONB migration for Postgres

    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_sysevt_type_time", "event_type", "occurred_at"),
        Index("idx_sysevt_feature_time", "feature", "occurred_at"),
    )

    def __repr__(self):
        return f"<SystemEvent(type='{self.event_type}', status='{self.status}')>"


class SystemMetricsDaily(Base):
    """
    Pre-aggregated daily snapshot.

    This is the PRIMARY table queried by the admin dashboard.
    Background worker writes to this every 15 minutes / nightly.
    """
    __tablename__ = "system_metrics_daily"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    metric_date             = Column(Date, nullable=False, unique=True, index=True)

    # Tenant counts
    total_orgs              = Column(Integer, default=0)
    active_orgs             = Column(Integer, default=0)
    inactive_orgs           = Column(Integer, default=0)
    new_orgs_today          = Column(Integer, default=0)

    # User counts (aggregated, no identity)
    total_users             = Column(Integer, default=0)
    active_users_today      = Column(Integer, default=0)   # users who made ≥1 request
    new_users_today         = Column(Integer, default=0)

    # Content volume (counts only, no per-tenant breakdown)
    total_documents         = Column(Integer, default=0)
    new_documents_today     = Column(Integer, default=0)
    total_cases             = Column(Integer, default=0)
    new_cases_today         = Column(Integer, default=0)

    # Activity
    ai_calls_today          = Column(Integer, default=0)
    api_requests_today      = Column(Integer, default=0)
    api_errors_today        = Column(Integer, default=0)
    avg_latency_ms          = Column(Float, default=0.0)
    p95_latency_ms          = Column(Float, default=0.0)

    # Feature usage: {"ai_chat": 120, "document_upload": 45, "risk_analysis": 30}
    # Keys = feature names; values = global call counts. NO org attribution.
    feature_usage           = Column(sa.Text, nullable=True)  # JSON string

    computed_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemMetricsDaily(date='{self.metric_date}', orgs={self.total_orgs})>"


class TenantCohort(Base):
    """
    Monthly tenant growth cohort.

    Tracks how many tenants registered / churned each month.
    No org names or IDs — just counts.
    """
    __tablename__ = "tenant_cohorts"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    cohort_month    = Column(Date, nullable=False, unique=True, index=True)
    # First day of month: e.g., date(2024, 3, 1)

    new_tenants     = Column(Integer, default=0)
    churned_tenants = Column(Integer, default=0)
    active_tenants  = Column(Integer, default=0)

    def __repr__(self):
        return f"<TenantCohort(month='{self.cohort_month}', new={self.new_tenants})>"
