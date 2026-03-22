"""
Alert Engine — checks upcoming/overdue deadlines and creates notifications.

Can be called periodically (cron / background task) or triggered after
a deadline is created/updated.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deadline import Deadline
from app.db.models.notification import Notification
from app.db.models.case import Case
from app.db.models.user import User, UserRole
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Default alert windows (days before deadline)
DEFAULT_ALERT_WINDOWS = [1, 3, 7]


class AlertEngine:

    async def check_deadlines(
        self,
        db: AsyncSession,
        organization_id: Optional[int] = None,
    ) -> int:
        """
        Scan all incomplete deadlines and create notifications for:
          - Overdue deadlines
          - Deadlines approaching within configured windows (1, 3, 7 days)

        Returns the number of notifications created.
        """
        now = datetime.utcnow()
        furthest_window = max(DEFAULT_ALERT_WINDOWS)
        cutoff = now + timedelta(days=furthest_window)

        filters = [
            Deadline.is_completed == False,
            Deadline.deadline_date <= cutoff,
            Deadline.alert_sent_at == None,
        ]
        if organization_id:
            filters.append(Deadline.organization_id == organization_id)

        result = await db.execute(
            select(Deadline).where(and_(*filters))
            .order_by(Deadline.deadline_date.asc())
        )
        deadlines = list(result.scalars().all())

        notifications_created = 0

        for deadline in deadlines:
            try:
                days_until = (deadline.deadline_date - now).total_seconds() / 86400.0
                is_overdue = days_until < 0

                # Determine if we should alert for this deadline
                should_alert = is_overdue  # Always alert for overdue
                if not should_alert:
                    for window in DEFAULT_ALERT_WINDOWS:
                        if days_until <= window:
                            should_alert = True
                            break

                if not should_alert:
                    continue

                # Build notification content
                if is_overdue:
                    alert_type = "deadline_overdue"
                    title = f"⚠️ Overdue: {deadline.title or deadline.description or 'Deadline'}"
                    message = f"Deadline was due {abs(int(days_until))} day(s) ago."
                else:
                    alert_type = "deadline_approaching"
                    days_text = f"{int(days_until)} day(s)" if days_until >= 1 else "less than 24 hours"
                    title = f"⏰ Approaching: {deadline.title or deadline.description or 'Deadline'}"
                    message = f"Deadline is due in {days_text}."

                # Determine who to notify
                recipients = await self._get_recipients(db, deadline)

                for user_id in recipients:
                    notification = Notification(
                        user_id=user_id,
                        organization_id=deadline.organization_id,
                        type=alert_type,
                        title=title,
                        message=message,
                        link=f"/cases/{deadline.case_id}" if deadline.case_id else None,
                        source_type="deadline",
                        source_id=deadline.id,
                    )
                    db.add(notification)
                    notifications_created += 1

                # Mark as alerted
                deadline.alert_sent_at = now

            except Exception as exc:
                logger.warning("Failed to process alert for deadline %d: %s", deadline.id, exc)
                continue

        await db.commit()
        logger.info("Alert engine created %d notifications.", notifications_created)
        return notifications_created

    async def check_all_organizations(self) -> int:
        """Run alert check across all organizations. Designed for background scheduling."""
        async with AsyncSessionLocal() as db:
            return await self.check_deadlines(db)

    async def _get_recipients(self, db: AsyncSession, deadline: Deadline) -> List[int]:
        """Determine who should receive a deadline notification."""
        recipients = set()

        # 1. The assigned user on the deadline (if any)
        if deadline.assignee_id:
            recipients.add(deadline.assignee_id)

        # 2. The assigned lawyer on the case (if any)
        if deadline.case_id:
            case = await db.get(Case, deadline.case_id)
            if case and case.assigned_lawyer_id:
                recipients.add(case.assigned_lawyer_id)

        # 3. Org admins for this organization
        if deadline.organization_id:
            result = await db.execute(
                select(User.id).where(
                    User.organization_id == deadline.organization_id,
                    User.role == UserRole.ORG_ADMIN,
                    User.is_active == True,
                )
            )
            for row in result.all():
                recipients.add(row[0])

        return list(recipients)


alert_engine = AlertEngine()
