"""
Case Event helpers — utility functions for recording timeline events.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case_event import CaseEvent


async def record_case_event(
    db: AsyncSession,
    case_id: int,
    event_type: str,
    description: str,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> CaseEvent:
    """
    Record a timeline event on a case.

    event_type values:
        case_created, document_added, deadline_created, deadline_completed,
        status_changed, lawyer_assigned, note_added
    """
    event = CaseEvent(
        case_id=case_id,
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        description=description,
        metadata_json=metadata_json,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
