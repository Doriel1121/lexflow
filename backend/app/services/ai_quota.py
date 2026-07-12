from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_usage_event import AIUsageEvent
from app.db.models.organization import Organization
from app.services.ai_quota_notifications import notify_ai_quota_threshold
from app.services.ai_usage_logger import estimate_tokens


DEFAULT_DAILY_CALL_LIMIT = 1000
DEFAULT_MONTHLY_DRAFTING_LIMIT = 100


@dataclass(frozen=True)
class AIQuotaStatus:
    limit_name: str
    used: int
    limit: int
    reset_at: datetime


class AIQuotaExceeded(Exception):
    def __init__(self, status: AIQuotaStatus):
        self.status = status
        super().__init__(
            f"AI quota exceeded for {status.limit_name}: {status.used}/{status.limit}"
        )


def is_drafting_task(task_type: str) -> bool:
    return (task_type or "").startswith("drafting.")


async def enforce_ai_quota(
    db: Optional[AsyncSession],
    *,
    organization_id: Optional[int],
    task_type: str,
    input_chars: Optional[int] = None,
) -> None:
    if db is None or organization_id is None:
        return

    org = await db.get(Organization, organization_id)
    if not org:
        return

    await _enforce_daily_calls(db, org)
    await _enforce_monthly_tokens(db, org, input_chars)
    if is_drafting_task(task_type):
        await _enforce_monthly_drafting(db, org)


async def _enforce_daily_calls(db: AsyncSession, org: Organization) -> None:
    limit = _effective_limit(org.ai_daily_call_limit, DEFAULT_DAILY_CALL_LIMIT)
    if limit is None:
        return

    since = datetime.utcnow() - timedelta(days=1)
    used = await _count_events(db, org.id, AIUsageEvent.created_at >= since)
    projected = used + 1
    reset_at = since + timedelta(days=1)
    await _notify_if_needed(
        org.id,
        limit_name="daily_ai_calls",
        used=projected,
        limit=limit,
        reset_at=reset_at,
        window_start=since,
    )
    if used >= limit:
        raise AIQuotaExceeded(
            AIQuotaStatus(
                limit_name="daily_ai_calls",
                used=used,
                limit=limit,
                reset_at=reset_at,
            )
        )


async def _enforce_monthly_drafting(db: AsyncSession, org: Organization) -> None:
    limit = _effective_limit(org.ai_monthly_drafting_limit, DEFAULT_MONTHLY_DRAFTING_LIMIT)
    if limit is None:
        return

    month_start = _utc_month_start()
    used = await _count_events(
        db,
        org.id,
        AIUsageEvent.created_at >= month_start,
        AIUsageEvent.task_type.like("drafting.%"),
    )
    projected = used + 1
    reset_at = _next_month_start(month_start)
    await _notify_if_needed(
        org.id,
        limit_name="monthly_drafting_calls",
        used=projected,
        limit=limit,
        reset_at=reset_at,
        window_start=month_start,
    )
    if used >= limit:
        raise AIQuotaExceeded(
            AIQuotaStatus(
                limit_name="monthly_drafting_calls",
                used=used,
                limit=limit,
                reset_at=reset_at,
            )
        )


async def _enforce_monthly_tokens(
    db: AsyncSession,
    org: Organization,
    input_chars: Optional[int],
) -> None:
    limit = _effective_limit(org.ai_monthly_token_limit, None)
    if limit is None:
        return

    month_start = _utc_month_start()
    current_tokens = int(
        (
            await db.execute(
                select(
                    func.coalesce(func.sum(AIUsageEvent.estimated_input_tokens), 0)
                    + func.coalesce(func.sum(AIUsageEvent.estimated_output_tokens), 0)
                ).where(
                    AIUsageEvent.organization_id == org.id,
                    AIUsageEvent.created_at >= month_start,
                )
            )
        ).scalar()
        or 0
    )
    requested_tokens = estimate_tokens(input_chars) or 0
    projected = current_tokens + requested_tokens
    reset_at = _next_month_start(month_start)
    await _notify_if_needed(
        org.id,
        limit_name="monthly_ai_tokens",
        used=projected,
        limit=limit,
        reset_at=reset_at,
        window_start=month_start,
    )
    if projected > limit:
        raise AIQuotaExceeded(
            AIQuotaStatus(
                limit_name="monthly_ai_tokens",
                used=projected,
                limit=limit,
                reset_at=reset_at,
            )
        )


async def _notify_if_needed(
    organization_id: int,
    *,
    limit_name: str,
    used: int,
    limit: int,
    reset_at: datetime,
    window_start: datetime,
) -> None:
    if limit <= 0:
        return
    usage_ratio = used / limit
    if usage_ratio >= 1:
        await notify_ai_quota_threshold(
            organization_id=organization_id,
            limit_name=limit_name,
            used=used,
            limit=limit,
            reset_at=reset_at,
            window_start=window_start,
            severity="hard_limit",
        )
    elif usage_ratio >= 0.8:
        await notify_ai_quota_threshold(
            organization_id=organization_id,
            limit_name=limit_name,
            used=used,
            limit=limit,
            reset_at=reset_at,
            window_start=window_start,
            severity="warning",
        )


async def _count_events(db: AsyncSession, organization_id: int, *filters) -> int:
    return int(
        (
            await db.execute(
                select(func.count(AIUsageEvent.id)).where(
                    AIUsageEvent.organization_id == organization_id,
                    *filters,
                )
            )
        ).scalar()
        or 0
    )


def _effective_limit(value: Optional[int], default: Optional[int]) -> Optional[int]:
    limit = default if value is None else value
    if limit is None or limit <= 0:
        return None
    return int(limit)


def _utc_month_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, 1)


def _next_month_start(month_start: datetime) -> datetime:
    if month_start.month == 12:
        return datetime(month_start.year + 1, 1, 1)
    return datetime(month_start.year, month_start.month + 1, 1)


async def get_ai_quota_snapshot(
    db: AsyncSession,
    *,
    organization_id: int,
) -> dict[str, object]:
    org = await db.get(Organization, organization_id)
    if not org:
        return {}

    daily_limit = _effective_limit(org.ai_daily_call_limit, DEFAULT_DAILY_CALL_LIMIT)
    monthly_drafting_limit = _effective_limit(
        org.ai_monthly_drafting_limit,
        DEFAULT_MONTHLY_DRAFTING_LIMIT,
    )
    monthly_token_limit = _effective_limit(org.ai_monthly_token_limit, None)
    rolling_day_start = datetime.utcnow() - timedelta(days=1)
    month_start = _utc_month_start()

    daily_used = await _count_events(db, org.id, AIUsageEvent.created_at >= rolling_day_start)
    monthly_drafting_used = await _count_events(
        db,
        org.id,
        AIUsageEvent.created_at >= month_start,
        AIUsageEvent.task_type.like("drafting.%"),
    )
    monthly_tokens_used = int(
        (
            await db.execute(
                select(
                    func.coalesce(func.sum(AIUsageEvent.estimated_input_tokens), 0)
                    + func.coalesce(func.sum(AIUsageEvent.estimated_output_tokens), 0)
                ).where(
                    AIUsageEvent.organization_id == org.id,
                    AIUsageEvent.created_at >= month_start,
                )
            )
        ).scalar()
        or 0
    )

    return {
        "daily_ai_calls": {
            "used": daily_used,
            "limit": daily_limit,
            "remaining": _remaining(daily_used, daily_limit),
            "reset_at": (rolling_day_start + timedelta(days=1)).isoformat(),
        },
        "monthly_drafting_calls": {
            "used": monthly_drafting_used,
            "limit": monthly_drafting_limit,
            "remaining": _remaining(monthly_drafting_used, monthly_drafting_limit),
            "reset_at": _next_month_start(month_start).isoformat(),
        },
        "monthly_ai_tokens": {
            "used": monthly_tokens_used,
            "limit": monthly_token_limit,
            "remaining": _remaining(monthly_tokens_used, monthly_token_limit),
            "reset_at": _next_month_start(month_start).isoformat(),
        },
    }


def _remaining(used: int, limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    return max(0, limit - used)
