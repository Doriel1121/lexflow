"""
Priority Engine — computes case priority scores based on deadline proximity,
case status, and activity level.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case, CaseStatus
from app.db.models.deadline import Deadline
from app.db.models.document import Document

logger = logging.getLogger(__name__)

# Priority weights
W_DEADLINE = 0.5   # deadline urgency weight
W_STATUS = 0.3     # case status weight
W_ACTIVITY = 0.2   # activity weight

# Priority label thresholds
PRIORITY_CRITICAL = 0.8
PRIORITY_HIGH = 0.5
PRIORITY_LOW = 0.2


class PriorityEngine:

    async def compute_priority(self, db: AsyncSession, case_id: int) -> float:
        """
        Calculate a priority score (0.0 – 1.0) for a case based on:
          - Nearest deadline urgency
          - Case status
          - Recent activity level (documents uploaded)
        """
        case = await db.get(Case, case_id)
        if not case:
            return 0.0

        deadline_score = await self._deadline_urgency(db, case_id)
        status_score = self._status_factor(case.status)
        activity_score = await self._activity_level(db, case_id)

        score = (W_DEADLINE * deadline_score +
                 W_STATUS * status_score +
                 W_ACTIVITY * activity_score)

        return round(min(max(score, 0.0), 1.0), 3)

    async def compute_and_store(self, db: AsyncSession, case_id: int) -> float:
        """Compute priority and persist it on the case record."""
        score = await self.compute_priority(db, case_id)
        case = await db.get(Case, case_id)
        if case:
            case.priority_score = score
            case.priority = self._score_to_label(score)
            await db.commit()
        return score

    async def recompute_all(self, db: AsyncSession, organization_id: int) -> int:
        """Recompute priorities for all open cases in an organization."""
        result = await db.execute(
            select(Case.id).where(
                Case.organization_id == organization_id,
                Case.status == CaseStatus.OPEN,
            )
        )
        case_ids = [row[0] for row in result.all()]
        for cid in case_ids:
            await self.compute_and_store(db, cid)
        logger.info("Recomputed priority for %d cases in org %d", len(case_ids), organization_id)
        return len(case_ids)

    # ── Scoring helpers ─────────────────────────────────────────────────

    async def _deadline_urgency(self, db: AsyncSession, case_id: int) -> float:
        """Score 0–1 based on the nearest incomplete deadline."""
        result = await db.execute(
            select(Deadline.deadline_date).where(
                Deadline.case_id == case_id,
                Deadline.is_completed == False,
            ).order_by(Deadline.deadline_date.asc()).limit(1)
        )
        row = result.first()
        if not row:
            return 0.0

        nearest_date = row[0]
        now = datetime.utcnow()

        if nearest_date <= now:
            # Overdue — maximum urgency
            return 1.0

        days_until = (nearest_date - now).total_seconds() / 86400.0

        if days_until <= 1:
            return 0.95
        elif days_until <= 3:
            return 0.8
        elif days_until <= 7:
            return 0.6
        elif days_until <= 14:
            return 0.35
        elif days_until <= 30:
            return 0.15
        else:
            return 0.05

    def _status_factor(self, status) -> float:
        """Score based on case status."""
        if hasattr(status, 'value'):
            status = status.value

        status_str = str(status).upper()
        if status_str == "PENDING":
            return 0.7
        elif status_str == "OPEN":
            return 0.5
        elif status_str == "CLOSED":
            return 0.0
        return 0.3

    async def _activity_level(self, db: AsyncSession, case_id: int) -> float:
        """Score based on recent document upload activity (last 7 days)."""
        week_ago = datetime.utcnow() - timedelta(days=7)
        count = await db.scalar(
            select(func.count(Document.id)).where(
                Document.case_id == case_id,
                Document.created_at >= week_ago,
            )
        ) or 0

        if count >= 5:
            return 0.9
        elif count >= 3:
            return 0.6
        elif count >= 1:
            return 0.3
        return 0.0

    def _score_to_label(self, score: float) -> str:
        """Convert numeric score to priority label."""
        if score >= PRIORITY_CRITICAL:
            return "critical"
        elif score >= PRIORITY_HIGH:
            return "high"
        elif score >= PRIORITY_LOW:
            return "normal"
        else:
            return "low"


priority_engine = PriorityEngine()
