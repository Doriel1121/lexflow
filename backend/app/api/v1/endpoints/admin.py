"""
api/v1/endpoints/admin.py  —  REDESIGNED (v2)
================================================
System Admin API — strictly aggregated, anonymized data only.

Removed endpoints (violated data isolation):
  ❌ GET  /admin/users                        (returned PII: email, name, org_id)
  ❌ GET  /admin/organizations                (returned org names, slugs, member counts)
  ❌ GET  /admin/organizations/{id}/details   (per-tenant analytics)
  ❌ GET  /admin/system-stats                 (legacy, replaced by /dashboard)

Kept / rewritten endpoints:
  ✅ GET  /admin/dashboard          — aggregated KPIs + chart data
  ✅ GET  /admin/growth             — tenant growth cohorts (counts only)
  ✅ GET  /admin/feature-usage      — global feature usage (no org attribution)
  ✅ GET  /admin/system-health      — health indicators
  ✅ GET  /admin/audit-logs         — anonymized logs (user_id hashed)
  ✅ POST /admin/organizations      — provision new tenant (legitimate write)

Security:
  - Every endpoint requires UserRole.ADMIN
  - No endpoint returns raw org/user data
  - Audit log user_id is replaced with SHA-256[:12] hash
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from pydantic import BaseModel, EmailStr

from app.core.dependencies import get_db, RoleChecker
from app.db.models.user import User, UserRole
from app.db.models.organization import Organization
from app.db.models.audit_log import AuditLog
from app.db.models.system_analytics import SystemMetricsDaily, TenantCohort
from app.schemas.admin import (
    AdminDashboardResponse,
    TenantStats, UserStats, ContentStats, ActivityStats, SystemHealthStatus,
    DailyMetricPoint, GrowthPoint, FeatureUsagePoint,
    AuditLogEntry, AuditLogsResponse,
    SystemGrowthResponse, FeatureUsageResponse,
)
from app.schemas.organization import OrganizationCreate
from app.schemas.user import UserCreate
from app.crud.organization import organization_crud
from app.crud.user import user_crud
from app.core.security import get_password_hash
from app.services.system_analytics import (
    get_last_n_daily_metrics,
    get_growth_cohorts,
    get_today_metrics,
    run_daily_aggregation,
)
import secrets

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_ONLY = RoleChecker([UserRole.ADMIN])


def _hash_user_id(user_id: Optional[int]) -> str:
    """Return a 12-char truncated SHA-256 of the real user_id.

    This is shown in audit logs so admins can spot repeated activity
    from the same actor without knowing who that actor is.
    """
    if user_id is None:
        return "anonymous"
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:12]


def _health_status(error_rate_pct: float, avg_latency_ms: float) -> str:
    if error_rate_pct > 10 or avg_latency_ms > 3000:
        return "critical"
    if error_rate_pct > 3 or avg_latency_ms > 1000:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# GET /admin/dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
):
    """
    System-wide KPIs + chart data for the admin dashboard.

    All values are aggregated. No org names, IDs, user emails, or any
    per-tenant breakdown is included in the response.
    """
    # Ensure today's snapshot exists (may be first hit of the day)
    today_snapshot = await get_today_metrics(db)
    if today_snapshot is None:
        # Run aggregation inline on first request of the day
        await run_daily_aggregation()
        today_snapshot = await get_today_metrics(db)

    # Last 30 days of daily metrics (for charts)
    last_30 = await get_last_n_daily_metrics(db, 30)
    last_30_sorted = sorted(last_30, key=lambda m: m.metric_date)

    # Last 12 months of growth cohorts
    cohorts = await get_growth_cohorts(db, 12)

    # ── Tenant stats ────────────────────────────────────────────────────────
    total_orgs = await db.scalar(select(func.count(Organization.id))) or 0
    active_orgs = await db.scalar(
        select(func.count(Organization.id)).where(Organization.is_active == True)
    ) or 0

    # New tenants this month
    month_start = datetime.utcnow().date().replace(day=1)
    new_this_month = await db.scalar(
        select(func.count(Organization.id)).where(
            Organization.created_at >= datetime.combine(month_start, datetime.min.time())
        )
    ) or 0

    tenant_stats = TenantStats(
        total_tenants=total_orgs,
        active_tenants=active_orgs,
        inactive_tenants=total_orgs - active_orgs,
        new_tenants_today=today_snapshot.new_orgs_today if today_snapshot else 0,
        new_tenants_this_month=new_this_month,
    )

    # ── User stats ───────────────────────────────────────────────────────────
    total_users = await db.scalar(select(func.count(User.id))) or 0
    avg_users_per_tenant = round(total_users / max(total_orgs, 1), 1)

    # Users by role — counts only, no org attribution
    users_by_role: dict[str, int] = {}
    for role in UserRole:
        if role == UserRole.ADMIN:
            continue  # don't expose how many system admins exist
        cnt = await db.scalar(
            select(func.count(User.id)).where(User.role == role)
        ) or 0
        users_by_role[role.value] = cnt

    user_stats = UserStats(
        total_users=total_users,
        active_users_today=today_snapshot.active_users_today if today_snapshot else 0,
        new_users_today=today_snapshot.new_users_today if today_snapshot else 0,
        avg_users_per_tenant=avg_users_per_tenant,
        users_by_role=users_by_role,
    )

    # ── Content stats ────────────────────────────────────────────────────────
    content_stats = ContentStats(
        total_documents=today_snapshot.total_documents if today_snapshot else 0,
        new_documents_today=today_snapshot.new_documents_today if today_snapshot else 0,
        total_cases=today_snapshot.total_cases if today_snapshot else 0,
        new_cases_today=today_snapshot.new_cases_today if today_snapshot else 0,
    )

    # ── Activity stats ───────────────────────────────────────────────────────
    api_req = today_snapshot.api_requests_today if today_snapshot else 0
    api_err = today_snapshot.api_errors_today if today_snapshot else 0
    error_rate = round((api_err / max(api_req, 1)) * 100, 2)
    avg_lat = today_snapshot.avg_latency_ms if today_snapshot else 0.0
    p95_lat = today_snapshot.p95_latency_ms if today_snapshot else 0.0

    activity_stats = ActivityStats(
        ai_calls_today=today_snapshot.ai_calls_today if today_snapshot else 0,
        api_requests_today=api_req,
        api_errors_today=api_err,
        error_rate_pct=error_rate,
        avg_latency_ms=round(avg_lat, 1),
        p95_latency_ms=round(p95_lat, 1),
    )

    system_health = SystemHealthStatus(
        status=_health_status(error_rate, avg_lat),
        error_rate_pct=error_rate,
        avg_latency_ms=round(avg_lat, 1),
        p95_latency_ms=round(p95_lat, 1),
        last_computed=today_snapshot.computed_at if today_snapshot else None,
    )

    # ── Time-series chart data ───────────────────────────────────────────────
    daily_api_calls = [
        DailyMetricPoint(date=m.metric_date, value=m.api_requests_today)
        for m in last_30_sorted
    ]
    daily_new_tenants = [
        DailyMetricPoint(date=m.metric_date, value=m.new_orgs_today)
        for m in last_30_sorted
    ]
    daily_error_rates = [
        DailyMetricPoint(
            date=m.metric_date,
            value=round((m.api_errors_today / max(m.api_requests_today, 1)) * 100, 2),
        )
        for m in last_30_sorted
    ]

    # ── Growth cohorts ───────────────────────────────────────────────────────
    growth_cohorts = [
        GrowthPoint(
            month=c.cohort_month.strftime("%Y-%m"),
            new_tenants=c.new_tenants,
            churned_tenants=c.churned_tenants,
            active_tenants=c.active_tenants,
        )
        for c in cohorts
    ]

    # ── Feature usage (last 7 days aggregate) ───────────────────────────────
    last_7 = last_30_sorted[-7:]
    feature_totals: dict[str, int] = {}
    for m in last_7:
        if m.feature_usage:
            try:
                parsed = json.loads(m.feature_usage)
                for feat, cnt in parsed.items():
                    feature_totals[feat] = feature_totals.get(feat, 0) + cnt
            except (json.JSONDecodeError, TypeError):
                pass

    feature_usage = [
        FeatureUsagePoint(feature=k, call_count=v)
        for k, v in sorted(feature_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return AdminDashboardResponse(
        computed_at=datetime.utcnow(),
        tenant_stats=tenant_stats,
        user_stats=user_stats,
        content_stats=content_stats,
        activity_stats=activity_stats,
        system_health=system_health,
        daily_api_calls=daily_api_calls,
        daily_new_tenants=daily_new_tenants,
        daily_error_rates=daily_error_rates,
        growth_cohorts=growth_cohorts,
        feature_usage=feature_usage,
    )


# ---------------------------------------------------------------------------
# GET /admin/growth
# ---------------------------------------------------------------------------

@router.get("/growth", response_model=SystemGrowthResponse)
async def get_growth(
    months: int = Query(default=12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
):
    """Monthly tenant growth (new / churned / active counts). No org identity."""
    cohorts = await get_growth_cohorts(db, months)
    return SystemGrowthResponse(
        cohorts=[
            GrowthPoint(
                month=c.cohort_month.strftime("%Y-%m"),
                new_tenants=c.new_tenants,
                churned_tenants=c.churned_tenants,
                active_tenants=c.active_tenants,
            )
            for c in cohorts
        ]
    )


# ---------------------------------------------------------------------------
# GET /admin/feature-usage
# ---------------------------------------------------------------------------

@router.get("/feature-usage", response_model=FeatureUsageResponse)
async def get_feature_usage(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
):
    """Global feature call counts for the last N days. No per-tenant attribution."""
    metrics = await get_last_n_daily_metrics(db, days)
    totals: dict[str, int] = {}
    for m in metrics:
        if m.feature_usage:
            try:
                for feat, cnt in json.loads(m.feature_usage).items():
                    totals[feat] = totals.get(feat, 0) + cnt
            except (json.JSONDecodeError, TypeError):
                pass

    items = [
        FeatureUsagePoint(feature=k, call_count=v)
        for k, v in sorted(totals.items(), key=lambda x: x[1], reverse=True)
    ]
    return FeatureUsageResponse(period_days=days, items=items)


# ---------------------------------------------------------------------------
# GET /admin/system-health
# ---------------------------------------------------------------------------

@router.get("/system-health", response_model=SystemHealthStatus)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
):
    """Current system health indicators."""
    today_snapshot = await get_today_metrics(db)
    if today_snapshot is None:
        return SystemHealthStatus(
            status="unknown",
            error_rate_pct=0.0,
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            last_computed=None,
        )

    api_req = today_snapshot.api_requests_today
    api_err = today_snapshot.api_errors_today
    error_rate = round((api_err / max(api_req, 1)) * 100, 2)

    return SystemHealthStatus(
        status=_health_status(error_rate, today_snapshot.avg_latency_ms),
        error_rate_pct=error_rate,
        avg_latency_ms=round(today_snapshot.avg_latency_ms, 1),
        p95_latency_ms=round(today_snapshot.p95_latency_ms, 1),
        last_computed=today_snapshot.computed_at,
    )


# ---------------------------------------------------------------------------
# GET /admin/audit-logs  (anonymized)
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=AuditLogsResponse)
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    event_type: Optional[str] = None,
):
    """
    System-wide audit log — anonymized.

    user_id is replaced with a 12-char SHA-256 hash.
    IP addresses are included for security monitoring.
    Org context is stripped entirely.
    """
    offset = (page - 1) * page_size
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if event_type:
        query = query.where(AuditLog.event_type == event_type)

    total = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.event_type == event_type if event_type else True
        )
    ) or 0

    result = await db.execute(query.offset(offset).limit(page_size))
    logs = result.scalars().all()

    return AuditLogsResponse(
        total=total,
        page=page,
        page_size=page_size,
        logs=[
            AuditLogEntry(
                id=log.id,
                timestamp=log.timestamp,
                user_hash=_hash_user_id(log.user_id),   # ← anonymized
                event_type=log.event_type,
                resource_type=log.resource_type,
                http_method=log.http_method,
                path=log.path,
                status_code=log.status_code,
                ip_address=log.ip_address,
                # organization_id intentionally omitted
            )
            for log in logs
        ],
    )


# ---------------------------------------------------------------------------
# POST /admin/organizations  (provisioning — legitimate write)
# ---------------------------------------------------------------------------

class AdminProvisionRequest(BaseModel):
    organization_name: str
    admin_email: EmailStr
    admin_name: str
    password: Optional[str] = None


@router.post("/organizations", status_code=201)
async def provision_organization(
    body: AdminProvisionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_ADMIN_ONLY),
):
    """
    Provision a new tenant organization + its first admin user.

    This is a write operation, not a read — it legitimately creates
    tenant data and returns only the minimum necessary confirmation.
    """
    existing = await user_crud.get_by_email(db, email=body.admin_email)
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    org_in = OrganizationCreate(name=body.organization_name)
    org = await organization_crud.create(db, obj_in=org_in)

    initial_password = body.password or secrets.token_urlsafe(14)
    new_user = UserCreate(
        email=body.admin_email,
        password=initial_password,
        full_name=body.admin_name,
        role=UserRole.ORG_ADMIN,
    )
    user = await user_crud.create(db, user_in=new_user, organization_id=org.id)

    return {
        "message": "Tenant provisioned successfully.",
        "organization": {"id": org.id, "name": org.name, "slug": org.slug},
        "admin_user": {
            "id": user.id,
            "email": user.email,
            "temporary_password": initial_password if not body.password else "[provided]",
        },
    }
