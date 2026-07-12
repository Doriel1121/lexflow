"""Organization-scoped AI usage telemetry."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RoleChecker, get_current_org, get_db
from app.db.models.ai_usage_event import AIUsageEvent
from app.db.models.user import User, UserRole
from app.services.ai_quota import get_ai_quota_snapshot

router = APIRouter(prefix="/org", tags=["org-ai-usage"])

_ORG_USAGE_ROLES = RoleChecker([UserRole.ORG_ADMIN])


@router.get("/ai-usage")
async def get_org_ai_usage(
    days: int = Query(30, ge=1, le=90),
    task_type: Optional[str] = Query(None, max_length=64),
    provider: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_USAGE_ROLES),
    org_id: Optional[int] = Depends(get_current_org),
):
    """
    Aggregated AI usage telemetry for the current user's organization.

    This endpoint intentionally returns aggregate counters only. It does not
    expose prompts, responses, document text, user emails, or other tenant data.
    """
    if org_id is None:
        raise HTTPException(status_code=400, detail="User is not assigned to an organization")

    since = datetime.utcnow() - timedelta(days=days)
    filters = [
        AIUsageEvent.organization_id == org_id,
        AIUsageEvent.created_at >= since,
    ]
    if task_type:
        filters.append(AIUsageEvent.task_type == task_type)
    if provider:
        filters.append(AIUsageEvent.provider == provider)
    if status:
        filters.append(AIUsageEvent.status == status)

    summary_row = (
        await db.execute(
            select(
                func.count(AIUsageEvent.id).label("total_calls"),
                func.sum(case((AIUsageEvent.status == "success", 1), else_=0)).label("success_calls"),
                func.sum(case((AIUsageEvent.status == "error", 1), else_=0)).label("error_calls"),
                func.avg(AIUsageEvent.latency_ms).label("avg_latency_ms"),
                func.sum(AIUsageEvent.estimated_input_tokens).label("estimated_input_tokens"),
                func.sum(AIUsageEvent.estimated_output_tokens).label("estimated_output_tokens"),
            ).where(*filters)
        )
    ).first()

    breakdown_rows = (
        await db.execute(
            select(
                AIUsageEvent.task_type,
                AIUsageEvent.provider,
                AIUsageEvent.model,
                AIUsageEvent.status,
                func.count(AIUsageEvent.id).label("calls"),
                func.avg(AIUsageEvent.latency_ms).label("avg_latency_ms"),
                func.max(AIUsageEvent.created_at).label("last_seen_at"),
                func.sum(AIUsageEvent.estimated_input_tokens).label("estimated_input_tokens"),
                func.sum(AIUsageEvent.estimated_output_tokens).label("estimated_output_tokens"),
            )
            .where(*filters)
            .group_by(
                AIUsageEvent.task_type,
                AIUsageEvent.provider,
                AIUsageEvent.model,
                AIUsageEvent.status,
            )
            .order_by(func.count(AIUsageEvent.id).desc())
            .limit(100)
        )
    ).all()

    total_calls = int(getattr(summary_row, "total_calls", 0) or 0) if summary_row else 0
    success_calls = int(getattr(summary_row, "success_calls", 0) or 0) if summary_row else 0
    error_calls = int(getattr(summary_row, "error_calls", 0) or 0) if summary_row else 0
    avg_latency = float(getattr(summary_row, "avg_latency_ms", 0) or 0) if summary_row else 0.0

    quota = await get_ai_quota_snapshot(db, organization_id=org_id)

    return {
        "window_days": days,
        "scope": "organization",
        "filters": {
            "task_type": task_type,
            "provider": provider,
            "status": status,
        },
        "quota": quota,
        "summary": {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "error_calls": error_calls,
            "avg_latency_ms": round(avg_latency, 1),
            "estimated_input_tokens": int(getattr(summary_row, "estimated_input_tokens", 0) or 0) if summary_row else 0,
            "estimated_output_tokens": int(getattr(summary_row, "estimated_output_tokens", 0) or 0) if summary_row else 0,
        },
        "breakdown": [
            {
                "task_type": row.task_type,
                "provider": row.provider,
                "model": row.model,
                "status": row.status,
                "calls": int(row.calls or 0),
                "avg_latency_ms": round(float(row.avg_latency_ms or 0), 1),
                "estimated_input_tokens": int(row.estimated_input_tokens or 0),
                "estimated_output_tokens": int(row.estimated_output_tokens or 0),
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            }
            for row in breakdown_rows
        ],
    }
