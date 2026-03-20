"""
services/system_analytics.py
==============================
Collects and aggregates system-level events for the admin dashboard.

Rules enforced here:
  - org_bucket  = hash(org_id)  % 10_000  — NEVER store real org_id
  - user_bucket = hash(user_id) % 10_000  — NEVER store real user_id
  - metadata dict passed in must never contain names, emails, slugs

Public API:
    track_event(...)          — fire-and-forget from endpoints / middleware
    run_daily_aggregation()   — called by background worker every 15 min + nightly
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models.system_analytics import SystemEvent, SystemMetricsDaily, TenantCohort
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.models.document import Document
from app.db.models.case import Case

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anonymize_id(real_id: Optional[int]) -> Optional[int]:
    """Hash a real DB integer ID into a safe bucket (0–9999).

    The bucket is NOT reversible and is NOT unique per org — it is used only
    for grouping/anonymizing activity patterns, never for identification.
    """
    if real_id is None:
        return None
    digest = hashlib.sha256(str(real_id).encode()).hexdigest()
    return int(digest[:8], 16) % 10_000


# ---------------------------------------------------------------------------
# Event tracking
# ---------------------------------------------------------------------------

async def track_event(
    *,
    event_type: str,
    feature: Optional[str] = None,
    org_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status: str = "success",
    latency_ms: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a single system event.

    This is fire-and-forget — errors are swallowed so they never impact
    the calling request.

    Args:
        event_type:  e.g. 'document.created', 'ai.call', 'user.login'
        feature:     e.g. 'document_upload', 'ai_chat', 'risk_analysis'
        org_id:      Real org ID — will be anonymized before storage.
        user_id:     Real user ID — will be anonymized before storage.
        status:      'success' | 'error' | 'timeout'
        latency_ms:  Request latency in milliseconds.
        extra:       Non-identifying supplementary data (no names/emails).
    """
    try:
        async with AsyncSessionLocal() as db:
            event = SystemEvent(
                event_type=event_type,
                feature=feature,
                org_bucket=_anonymize_id(org_id),
                user_bucket=_anonymize_id(user_id),
                status=status,
                latency_ms=latency_ms,
                extra=json.dumps(extra) if extra else None,
                occurred_at=datetime.utcnow(),
            )
            db.add(event)
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("track_event failed silently: %s", exc)


# ---------------------------------------------------------------------------
# Daily aggregation worker
# ---------------------------------------------------------------------------

async def run_daily_aggregation(target_date: Optional[date] = None) -> None:
    """
    Aggregate raw events + DB counts into SystemMetricsDaily.

    Designed to be idempotent — upserts the row for `target_date`.
    Called:
      - Every 15 minutes by the background reaper loop (for today).
      - Once nightly for yesterday (final snapshot).

    Args:
        target_date: Date to aggregate. Defaults to today (UTC).
    """
    today = target_date or datetime.utcnow().date()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    day_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    try:
        async with AsyncSessionLocal() as db:
            # ── Tenant counts (direct DB, counts only) ──────────────────────
            total_orgs = await db.scalar(select(func.count(Organization.id))) or 0
            active_orgs = await db.scalar(
                select(func.count(Organization.id)).where(Organization.is_active == True)
            ) or 0
            inactive_orgs = total_orgs - active_orgs

            new_orgs_today = await db.scalar(
                select(func.count(Organization.id)).where(
                    Organization.created_at >= day_start,
                    Organization.created_at <= day_end,
                )
            ) or 0

            # ── User counts ─────────────────────────────────────────────────
            total_users = await db.scalar(select(func.count(User.id))) or 0
            new_users_today = await db.scalar(
                select(func.count(User.id)).where(
                    User.created_at >= day_start,
                    User.created_at <= day_end,
                )
            ) or 0

            # ── Content volume counts ────────────────────────────────────────
            total_documents = await db.scalar(select(func.count(Document.id))) or 0
            new_docs_today = await db.scalar(
                select(func.count(Document.id)).where(
                    Document.created_at >= day_start,
                    Document.created_at <= day_end,
                )
            ) or 0

            total_cases = await db.scalar(select(func.count(Case.id))) or 0
            new_cases_today = await db.scalar(
                select(func.count(Case.id)).where(
                    Case.created_at >= day_start,
                    Case.created_at <= day_end,
                )
            ) or 0

            # ── Event-based metrics (from system_events) ─────────────────────
            # Active users today: distinct user_buckets that had an event
            active_users_today = await db.scalar(
                select(func.count(func.distinct(SystemEvent.user_bucket))).where(
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                    SystemEvent.user_bucket.isnot(None),
                )
            ) or 0

            ai_calls_today = await db.scalar(
                select(func.count(SystemEvent.id)).where(
                    SystemEvent.event_type == "ai.call",
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                )
            ) or 0

            api_requests_today = await db.scalar(
                select(func.count(SystemEvent.id)).where(
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                )
            ) or 0

            api_errors_today = await db.scalar(
                select(func.count(SystemEvent.id)).where(
                    SystemEvent.status == "error",
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                )
            ) or 0

            # Latency metrics
            avg_latency = await db.scalar(
                select(func.avg(SystemEvent.latency_ms)).where(
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                    SystemEvent.latency_ms.isnot(None),
                )
            ) or 0.0

            # P95 latency via percentile_cont (Postgres) or approximation
            try:
                p95_result = await db.scalar(
                    text(
                        "SELECT percentile_cont(0.95) WITHIN GROUP "
                        "(ORDER BY latency_ms) FROM system_events "
                        "WHERE occurred_at BETWEEN :s AND :e "
                        "AND latency_ms IS NOT NULL"
                    ).bindparams(s=day_start, e=day_end)
                )
                p95_latency = float(p95_result or 0)
            except Exception:
                # SQLite fallback: use avg * 1.5 as rough estimate
                p95_latency = float(avg_latency) * 1.5

            # ── Feature usage breakdown ───────────────────────────────────────
            feature_result = await db.execute(
                select(SystemEvent.feature, func.count(SystemEvent.id).label("cnt"))
                .where(
                    SystemEvent.occurred_at >= day_start,
                    SystemEvent.occurred_at <= day_end,
                    SystemEvent.feature.isnot(None),
                )
                .group_by(SystemEvent.feature)
            )
            feature_usage: Dict[str, int] = {
                row.feature: row.cnt for row in feature_result
            }

            # ── Upsert SystemMetricsDaily ─────────────────────────────────────
            existing = await db.scalar(
                select(SystemMetricsDaily).where(SystemMetricsDaily.metric_date == today)
            )

            if existing:
                existing.total_orgs = total_orgs
                existing.active_orgs = active_orgs
                existing.inactive_orgs = inactive_orgs
                existing.new_orgs_today = new_orgs_today
                existing.total_users = total_users
                existing.active_users_today = active_users_today
                existing.new_users_today = new_users_today
                existing.total_documents = total_documents
                existing.new_documents_today = new_docs_today
                existing.total_cases = total_cases
                existing.new_cases_today = new_cases_today
                existing.ai_calls_today = ai_calls_today
                existing.api_requests_today = api_requests_today
                existing.api_errors_today = api_errors_today
                existing.avg_latency_ms = float(avg_latency)
                existing.p95_latency_ms = p95_latency
                existing.feature_usage = json.dumps(feature_usage)
                existing.computed_at = datetime.utcnow()
            else:
                db.add(SystemMetricsDaily(
                    metric_date=today,
                    total_orgs=total_orgs,
                    active_orgs=active_orgs,
                    inactive_orgs=inactive_orgs,
                    new_orgs_today=new_orgs_today,
                    total_users=total_users,
                    active_users_today=active_users_today,
                    new_users_today=new_users_today,
                    total_documents=total_documents,
                    new_documents_today=new_docs_today,
                    total_cases=total_cases,
                    new_cases_today=new_cases_today,
                    ai_calls_today=ai_calls_today,
                    api_requests_today=api_requests_today,
                    api_errors_today=api_errors_today,
                    avg_latency_ms=float(avg_latency),
                    p95_latency_ms=p95_latency,
                    feature_usage=json.dumps(feature_usage),
                ))

            await db.commit()

        # ── Update tenant cohort for this month ──────────────────────────────
        await _update_tenant_cohort(today)

        logger.info("Daily aggregation complete for %s", today)

    except Exception as exc:
        logger.error("run_daily_aggregation failed for %s: %s", today, exc)
        raise


async def _update_tenant_cohort(target_date: date) -> None:
    """Upsert monthly tenant cohort row. Counts only — no org identity."""
    cohort_month = target_date.replace(day=1)
    month_end = (cohort_month + timedelta(days=32)).replace(day=1)

    async with AsyncSessionLocal() as db:
        new_tenants = await db.scalar(
            select(func.count(Organization.id)).where(
                Organization.created_at >= datetime.combine(cohort_month, datetime.min.time()),
                Organization.created_at < datetime.combine(month_end, datetime.min.time()),
            )
        ) or 0

        active_tenants = await db.scalar(
            select(func.count(Organization.id)).where(Organization.is_active == True)
        ) or 0

        existing = await db.scalar(
            select(TenantCohort).where(TenantCohort.cohort_month == cohort_month)
        )
        if existing:
            existing.new_tenants = new_tenants
            existing.active_tenants = active_tenants
        else:
            db.add(TenantCohort(
                cohort_month=cohort_month,
                new_tenants=new_tenants,
                churned_tenants=0,
                active_tenants=active_tenants,
            ))
        await db.commit()


# ---------------------------------------------------------------------------
# Query helpers (used by admin API endpoints)
# ---------------------------------------------------------------------------

async def get_last_n_daily_metrics(
    db: AsyncSession, n: int = 30
) -> list[SystemMetricsDaily]:
    """Return the last N days of aggregated metrics (newest first)."""
    result = await db.execute(
        select(SystemMetricsDaily)
        .order_by(SystemMetricsDaily.metric_date.desc())
        .limit(n)
    )
    return list(result.scalars().all())


async def get_growth_cohorts(
    db: AsyncSession, months: int = 12
) -> list[TenantCohort]:
    """Return the last N months of tenant growth data."""
    cutoff = datetime.utcnow().date().replace(day=1)
    # Go back `months` months
    for _ in range(months - 1):
        cutoff = (cutoff - timedelta(days=1)).replace(day=1)

    result = await db.execute(
        select(TenantCohort)
        .where(TenantCohort.cohort_month >= cutoff)
        .order_by(TenantCohort.cohort_month.asc())
    )
    return list(result.scalars().all())


async def get_today_metrics(db: AsyncSession) -> Optional[SystemMetricsDaily]:
    """Return today's metrics snapshot (may be partial if aggregation hasn't run yet)."""
    today = datetime.utcnow().date()
    return await db.scalar(
        select(SystemMetricsDaily).where(SystemMetricsDaily.metric_date == today)
    )
