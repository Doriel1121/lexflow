"""
Org Analytics Service — provides organization-scoped employee performance
analytics for the org_admin dashboard.

All queries are scoped to a single organization_id. No cross-org data leakage.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserRole
from app.db.models.case import Case, CaseStatus
from app.db.models.document import Document
from app.db.models.deadline import Deadline
from app.db.models.case_event import CaseEvent

logger = logging.getLogger(__name__)


class OrgAnalyticsService:

    async def get_org_summary(self, db: AsyncSession, org_id: int) -> Dict[str, Any]:
        """
        Org-wide aggregate stats for the admin dashboard.
        """
        now = datetime.utcnow()

        # ── Case counts ───────────────────────────────────────────────
        total_cases = await db.scalar(
            select(func.count(Case.id)).where(Case.organization_id == org_id)
        ) or 0

        open_cases = await db.scalar(
            select(func.count(Case.id)).where(
                Case.organization_id == org_id,
                Case.status == CaseStatus.OPEN,
            )
        ) or 0

        pending_cases = await db.scalar(
            select(func.count(Case.id)).where(
                Case.organization_id == org_id,
                Case.status == CaseStatus.PENDING,
            )
        ) or 0

        closed_cases = await db.scalar(
            select(func.count(Case.id)).where(
                Case.organization_id == org_id,
                Case.status == CaseStatus.CLOSED,
            )
        ) or 0

        # ── Unassigned cases ──────────────────────────────────────────
        unassigned_cases = await db.scalar(
            select(func.count(Case.id)).where(
                Case.organization_id == org_id,
                Case.status != CaseStatus.CLOSED,
                Case.assigned_lawyer_id == None,
            )
        ) or 0

        # ── Document count ────────────────────────────────────────────
        total_documents = await db.scalar(
            select(func.count(Document.id)).where(Document.organization_id == org_id)
        ) or 0

        # ── Deadline stats ────────────────────────────────────────────
        overdue_deadlines = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == False,
                Deadline.deadline_date < now,
            )
        ) or 0

        upcoming_deadlines_7d = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == False,
                Deadline.deadline_date >= now,
                Deadline.deadline_date <= now + timedelta(days=7),
            )
        ) or 0

        total_completed_deadlines = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == True,
            )
        ) or 0

        total_deadlines = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
            )
        ) or 0

        compliance_rate = round(
            (total_completed_deadlines / max(total_deadlines, 1)) * 100, 1
        )

        # ── Document upload trend (last 30 days) ──────────────────────
        upload_trend = await self._get_daily_counts(
            db, Document, Document.organization_id == org_id, days=30
        )

        # ── Classification breakdown ──────────────────────────────────
        classification_result = await db.execute(
            select(
                Document.classification,
                func.count(Document.id).label("cnt"),
            ).where(
                Document.organization_id == org_id,
                Document.classification != None,
            ).group_by(Document.classification)
        )
        classification_breakdown = {
            row.classification: row.cnt for row in classification_result.all()
        }

        return {
            "total_cases": total_cases,
            "open_cases": open_cases,
            "pending_cases": pending_cases,
            "closed_cases": closed_cases,
            "unassigned_cases": unassigned_cases,
            "total_documents": total_documents,
            "overdue_deadlines": overdue_deadlines,
            "upcoming_deadlines_7d": upcoming_deadlines_7d,
            "deadline_compliance_rate": compliance_rate,
            "upload_trend": upload_trend,
            "classification_breakdown": classification_breakdown,
        }

    async def get_employee_stats(
        self, db: AsyncSession, org_id: int
    ) -> List[Dict[str, Any]]:
        """
        Per-employee (lawyer/assistant) performance stats.
        Returns a list of dicts, one per team member.
        """
        now = datetime.utcnow()

        # Get all team members (lawyers + assistants) in this org
        result = await db.execute(
            select(User).where(
                User.organization_id == org_id,
                User.is_active == True,
                User.role.in_([UserRole.LAWYER, UserRole.ASSISTANT, UserRole.ORG_ADMIN]),
            ).order_by(User.full_name)
        )
        members = list(result.scalars().all())

        employee_data = []
        for member in members:
            uid = member.id

            # Assigned open cases
            open_cases = await db.scalar(
                select(func.count(Case.id)).where(
                    Case.organization_id == org_id,
                    Case.assigned_lawyer_id == uid,
                    Case.status == CaseStatus.OPEN,
                )
            ) or 0

            # Total assigned cases
            total_assigned = await db.scalar(
                select(func.count(Case.id)).where(
                    Case.organization_id == org_id,
                    Case.assigned_lawyer_id == uid,
                )
            ) or 0

            # Documents uploaded
            docs_uploaded = await db.scalar(
                select(func.count(Document.id)).where(
                    Document.organization_id == org_id,
                    Document.uploaded_by_user_id == uid,
                )
            ) or 0

            # Deadline compliance for this user's deadlines
            user_total_deadlines = await db.scalar(
                select(func.count(Deadline.id)).where(
                    Deadline.organization_id == org_id,
                    Deadline.assignee_id == uid,
                )
            ) or 0

            user_completed_deadlines = await db.scalar(
                select(func.count(Deadline.id)).where(
                    Deadline.organization_id == org_id,
                    Deadline.assignee_id == uid,
                    Deadline.is_completed == True,
                )
            ) or 0

            user_overdue = await db.scalar(
                select(func.count(Deadline.id)).where(
                    Deadline.organization_id == org_id,
                    Deadline.assignee_id == uid,
                    Deadline.is_completed == False,
                    Deadline.deadline_date < now,
                )
            ) or 0

            compliance_rate = round(
                (user_completed_deadlines / max(user_total_deadlines, 1)) * 100, 1
            )

            # Last activity (most recent case event by this user)
            last_event = await db.scalar(
                select(func.max(CaseEvent.created_at)).where(
                    CaseEvent.organization_id == org_id,
                    CaseEvent.user_id == uid,
                )
            )

            # Cases created this month
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cases_this_month = await db.scalar(
                select(func.count(Case.id)).where(
                    Case.organization_id == org_id,
                    Case.created_by_user_id == uid,
                    Case.created_at >= month_start,
                )
            ) or 0

            employee_data.append({
                "user_id": uid,
                "full_name": member.full_name or member.email,
                "email": member.email,
                "role": member.role.value if member.role else "lawyer",
                "open_cases": open_cases,
                "total_assigned_cases": total_assigned,
                "documents_uploaded": docs_uploaded,
                "deadline_compliance_rate": compliance_rate,
                "total_deadlines": user_total_deadlines,
                "completed_deadlines": user_completed_deadlines,
                "overdue_deadlines": user_overdue,
                "last_activity": last_event.isoformat() if last_event else None,
                "cases_created_this_month": cases_this_month,
            })

        return employee_data

    async def get_workload_distribution(
        self, db: AsyncSession, org_id: int
    ) -> List[Dict[str, Any]]:
        """
        Returns case distribution per lawyer (for workload chart).
        """
        result = await db.execute(
            select(
                User.id,
                User.full_name,
                func.count(Case.id).label("case_count"),
            )
            .outerjoin(Case, and_(
                Case.assigned_lawyer_id == User.id,
                Case.status != CaseStatus.CLOSED,
            ))
            .where(
                User.organization_id == org_id,
                User.is_active == True,
                User.role.in_([UserRole.LAWYER, UserRole.ASSISTANT, UserRole.ORG_ADMIN]),
            )
            .group_by(User.id, User.full_name)
            .order_by(func.count(Case.id).desc())
        )

        return [
            {
                "user_id": row.id,
                "full_name": row.full_name or "Unknown",
                "case_count": row.case_count,
            }
            for row in result.all()
        ]

    async def get_deadline_health(
        self, db: AsyncSession, org_id: int
    ) -> Dict[str, Any]:
        """
        Deadline health summary: overdue, approaching, on-track counts.
        """
        now = datetime.utcnow()

        overdue = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == False,
                Deadline.deadline_date < now,
            )
        ) or 0

        approaching = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == False,
                Deadline.deadline_date >= now,
                Deadline.deadline_date <= now + timedelta(days=7),
            )
        ) or 0

        on_track = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == False,
                Deadline.deadline_date > now + timedelta(days=7),
            )
        ) or 0

        completed = await db.scalar(
            select(func.count(Deadline.id)).where(
                Deadline.organization_id == org_id,
                Deadline.is_completed == True,
            )
        ) or 0

        # Compliance trend (last 30 days, weekly buckets)
        compliance_trend = []
        for weeks_ago in range(4, -1, -1):
            week_start = now - timedelta(weeks=weeks_ago + 1)
            week_end = now - timedelta(weeks=weeks_ago)

            week_total = await db.scalar(
                select(func.count(Deadline.id)).where(
                    Deadline.organization_id == org_id,
                    Deadline.deadline_date >= week_start,
                    Deadline.deadline_date < week_end,
                )
            ) or 0

            week_completed = await db.scalar(
                select(func.count(Deadline.id)).where(
                    Deadline.organization_id == org_id,
                    Deadline.deadline_date >= week_start,
                    Deadline.deadline_date < week_end,
                    Deadline.is_completed == True,
                )
            ) or 0

            rate = round((week_completed / max(week_total, 1)) * 100, 1)
            compliance_trend.append({
                "week_start": week_start.date().isoformat(),
                "total": week_total,
                "completed": week_completed,
                "rate": rate,
            })

        return {
            "overdue": overdue,
            "approaching": approaching,
            "on_track": on_track,
            "completed": completed,
            "compliance_trend": compliance_trend,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    async def _get_daily_counts(
        self, db: AsyncSession, model, org_filter, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get daily creation counts for a model over the last N days."""
        now = datetime.utcnow()
        trend = []
        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            count = await db.scalar(
                select(func.count(model.id)).where(
                    org_filter,
                    model.created_at >= day_start,
                    model.created_at < day_end,
                )
            ) or 0

            trend.append({
                "date": day_start.date().isoformat(),
                "count": count,
            })
        return trend


org_analytics_service = OrgAnalyticsService()
