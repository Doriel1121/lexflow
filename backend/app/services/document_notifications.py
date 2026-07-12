"""Org-wide document processing notifications (DB + Redis WebSocket)."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.db.models.user import User

logger = logging.getLogger(__name__)


def publish_notification_for_users(org_user_ids: list[int], message: dict) -> None:
    from app.api.ws.notifications import publish_notification_sync

    for user_id in org_user_ids:
        publish_notification_sync(user_id, message)


async def create_org_notification(
    db: AsyncSession,
    *,
    organization_id: int,
    event_type: str,
    title: str,
    message: str,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    extra_payload: Optional[dict] = None,
) -> int:
    result = await db.execute(select(User.id).where(User.organization_id == organization_id))
    org_user_ids = list(result.scalars().all())

    for org_user_id in org_user_ids:
        db.add(
            Notification(
                user_id=org_user_id,
                organization_id=organization_id,
                type=event_type,
                title=title,
                message=message,
                source_type=source_type,
                source_id=source_id,
                read=False,
            )
        )

    await db.commit()

    ws_payload = {
        "type": event_type,
        "title": title,
        "message": message,
        "source_type": source_type,
    }
    if source_type == "document" and source_id is not None:
        ws_payload["document_id"] = source_id
    if isinstance(extra_payload, dict) and extra_payload:
        # Allow callers to include additional fields (e.g., stage/progress/status)
        ws_payload.update(extra_payload)

    publish_notification_for_users(org_user_ids, ws_payload)

    logger.info(
        "[Doc %s] Persisted %s '%s' notifications for org %s",
        source_id,
        len(org_user_ids),
        event_type,
        organization_id,
    )
    return len(org_user_ids)


async def emit_document_status_update(
    db: AsyncSession,
    *,
    organization_id: int,
    document_id: int,
    stage: str,
    progress: float,
    status: str = "processing",
) -> None:
    """Emit real-time WebSocket progress update without creating DB notification rows."""
    try:
        result = await db.execute(select(User.id).where(User.organization_id == organization_id))
        org_user_ids = list(result.scalars().all())

        ws_payload = {
            "type": "DOCUMENT_STATUS_UPDATE",
            "document_id": document_id,
            "stage": stage,
            "progress": round(float(progress), 1),
            "status": status,
        }
        publish_notification_for_users(org_user_ids, ws_payload)
        logger.debug("[Doc %s] Emitted WebSocket status update: stage=%s, progress=%s%%", document_id, stage, progress)
    except Exception as e:
        logger.warning("[Doc %s] Failed to emit WebSocket status update: %s", document_id, e)

