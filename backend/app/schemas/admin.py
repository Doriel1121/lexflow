"""
schemas/admin.py  —  REDESIGNED (v2)
======================================
All schemas here are strictly system-level aggregates.

Rules:
  ❌ No org names, org IDs, org slugs
  ❌ No user emails, user names, user IDs
  ❌ No per-tenant breakdowns (no dict keyed by org/user ID)
  ✅ Global counts, rates, and time-series only
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

class TenantStats(BaseModel):
    """Aggregated tenant (organization) counts — no names or IDs."""
    total_tenants: int
    active_tenants: int
    inactive_tenants: int
    new_tenants_today: int
    new_tenants_this_month: int


class UserStats(BaseModel):
    """Aggregated user counts — no emails, names, or individual IDs."""
    total_users: int
    active_users_today: int
    new_users_today: int
    avg_users_per_tenant: float
    users_by_role: Dict[str, int]
    # e.g. {"org_admin": 12, "lawyer": 80, "viewer": 30}
    # Keys are role names (generic), no org attribution


class ContentStats(BaseModel):
    """System-wide content volume — counts only, no per-tenant data."""
    total_documents: int
    new_documents_today: int
    total_cases: int
    new_cases_today: int


# ---------------------------------------------------------------------------
# Activity & Health
# ---------------------------------------------------------------------------

class ActivityStats(BaseModel):
    """System-wide activity for today."""
    ai_calls_today: int
    api_requests_today: int
    api_errors_today: int
    error_rate_pct: float = Field(
        description="Percentage of requests that returned an error today"
    )
    avg_latency_ms: float
    p95_latency_ms: float


class SystemHealthStatus(BaseModel):
    """High-level system health indicators."""
    status: str  # 'healthy' | 'degraded' | 'critical'
    error_rate_pct: float
    avg_latency_ms: float
    p95_latency_ms: float
    last_computed: Optional[datetime]


# ---------------------------------------------------------------------------
# Time-series for charts
# ---------------------------------------------------------------------------

class DailyMetricPoint(BaseModel):
    """Single data point in a time-series chart."""
    date: date
    value: float


class GrowthPoint(BaseModel):
    """Monthly growth chart data point."""
    month: str          # e.g. "2024-03"
    new_tenants: int
    churned_tenants: int
    active_tenants: int


class FeatureUsagePoint(BaseModel):
    """Single bar in a feature usage chart."""
    feature: str        # e.g. "ai_chat", "document_upload"
    call_count: int


# ---------------------------------------------------------------------------
# Audit logs (anonymized)
# ---------------------------------------------------------------------------

class AuditLogEntry(BaseModel):
    """
    Anonymized audit log entry for system admin view.
    user_id is replaced with a truncated hash — NOT the real ID.
    org context is bucketed — NOT the real org ID.
    """
    id: int
    timestamp: datetime
    user_hash: str          # SHA-256[:12] of real user_id — irreversible
    event_type: str
    resource_type: Optional[str]
    http_method: Optional[str]
    path: Optional[str]
    status_code: Optional[int]
    ip_address: Optional[str]


# ---------------------------------------------------------------------------
# Main dashboard response
# ---------------------------------------------------------------------------

class AdminDashboardResponse(BaseModel):
    """
    Complete system admin dashboard payload.

    Every field here is either:
    - A global aggregate (a single integer/float)
    - A time-series of global aggregates
    - An anonymized log entry

    Nothing in this model can be traced back to a specific tenant or user.
    """
    computed_at: datetime

    # KPI cards
    tenant_stats: TenantStats
    user_stats: UserStats
    content_stats: ContentStats
    activity_stats: ActivityStats
    system_health: SystemHealthStatus

    # Chart data
    daily_api_calls: List[DailyMetricPoint]       # last 30 days
    daily_new_tenants: List[DailyMetricPoint]     # last 30 days
    daily_error_rates: List[DailyMetricPoint]     # last 30 days (%)
    growth_cohorts: List[GrowthPoint]             # last 12 months
    feature_usage: List[FeatureUsagePoint]        # last 7 days, aggregated


class SystemGrowthResponse(BaseModel):
    """Tenant growth chart data."""
    cohorts: List[GrowthPoint]


class FeatureUsageResponse(BaseModel):
    """Feature usage breakdown."""
    period_days: int
    items: List[FeatureUsagePoint]


class AuditLogsResponse(BaseModel):
    """Paginated anonymized audit log."""
    total: int
    page: int
    page_size: int
    logs: List[AuditLogEntry]
