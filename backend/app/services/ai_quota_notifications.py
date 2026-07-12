from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import select

from app.db.models.notification import Notification
from app.db.models.user import User, UserRole
from app.db.session import CeleryAsyncSessionLocal

logger = logging.getLogger(__name__)

QuotaSeverity = Literal["warning", "hard_limit"]


async def notify_ai_quota_threshold(
    *,
    organization_id: int,
    limit_name: str,
    used: int,
    limit: int,
    reset_at: datetime,
    window_start: datetime,
    severity: QuotaSeverity,
) -> int:
    """
    Notify org admins once per quota/window/severity.

    Uses a separate DB session so quota alerts are not lost if the AI request
    itself raises a 429 after the notification is created.
    """
    if limit <= 0:
        return 0

    event_type = f"ai_quota_{severity}"
    title = _title(limit_name, severity)
    message = _message(limit_name, used, limit, reset_at, severity)

    try:
        async with CeleryAsyncSessionLocal() as db:
            existing = await db.execute(
                select(Notification.id)
                .where(
                    Notification.organization_id == organization_id,
                    Notification.type == event_type,
                    Notification.source_type == "ai_quota",
                    Notification.title == title,
                    Notification.created_at >= window_start,
                )
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return 0

            recipients_res = await db.execute(
                select(User.id).where(
                    User.organization_id == organization_id,
                    User.role == UserRole.ORG_ADMIN,
                    User.is_active == True,
                )
            )
            recipient_ids = list(recipients_res.scalars().all())
            if not recipient_ids:
                return 0

            for user_id in recipient_ids:
                db.add(
                    Notification(
                        user_id=user_id,
                        organization_id=organization_id,
                        type=event_type,
                        title=title,
                        message=message,
                        link="/settings/ai-usage",
                        source_type="ai_quota",
                        read=False,
                    )
                )
            await db.commit()

        from app.api.ws.notifications import publish_notification_sync

        for user_id in recipient_ids:
            publish_notification_sync(
                user_id,
                {
                    "type": event_type,
                    "title": title,
                    "message": message,
                    "link": "/settings/ai-usage",
                    "source_type": "ai_quota",
                    "limit_name": limit_name,
                    "used": used,
                    "limit": limit,
                    "reset_at": reset_at.isoformat(),
                },
            )

        return len(recipient_ids)
    except Exception as exc:
        logger.warning("Failed to create AI quota notification: %s", exc)
        return 0


def _title(limit_name: str, severity: QuotaSeverity) -> str:
    label = _label(limit_name)
    if severity == "hard_limit":
        return f"AI quota reached: {label}"
    return f"AI quota warning: {label}"


def _message(
    limit_name: str,
    used: int,
    limit: int,
    reset_at: datetime,
    severity: QuotaSeverity,
) -> str:
    label = _label(limit_name)
    percent = min(100, round((used / limit) * 100)) if limit else 0
    reset_text = reset_at.strftime("%Y-%m-%d %H:%M UTC")
    if severity == "hard_limit":
        return f"{label} has reached its limit ({used}/{limit}). AI actions may be blocked until {reset_text}."
    return f"{label} is at {percent}% of its limit ({used}/{limit}). Limit resets at {reset_text}."


def _label(limit_name: str) -> str:
    return {
        "daily_ai_calls": "Daily AI calls",
        "monthly_drafting_calls": "Monthly drafting calls",
        "monthly_ai_tokens": "Monthly AI tokens",
    }.get(limit_name, limit_name.replace("_", " ").title())
