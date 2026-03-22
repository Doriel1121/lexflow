"""
Org Analytics API — organization-scoped employee and performance analytics.

All endpoints require org_admin role and are scoped to the current user's organization.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_org, RoleChecker
from app.db.models.user import User, UserRole
from app.services.org_analytics import org_analytics_service

router = APIRouter(prefix="/org/analytics", tags=["org-analytics"])

_ORG_ADMIN_ONLY = RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN])


@router.get("/summary")
async def get_org_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ADMIN_ONLY),
    org_id: int = Depends(get_current_org),
):
    """
    Organization-wide aggregate stats: cases, documents, deadlines,
    compliance rates, upload trends, classification breakdown.
    """
    return await org_analytics_service.get_org_summary(db, org_id)


@router.get("/employees")
async def get_employee_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ADMIN_ONLY),
    org_id: int = Depends(get_current_org),
):
    """
    Per-employee performance: open cases, documents uploaded,
    deadline compliance, overdue count, last activity.
    """
    return await org_analytics_service.get_employee_stats(db, org_id)


@router.get("/workload")
async def get_workload_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ADMIN_ONLY),
    org_id: int = Depends(get_current_org),
):
    """
    Workload chart data: cases-per-lawyer distribution.
    """
    return await org_analytics_service.get_workload_distribution(db, org_id)


@router.get("/deadlines")
async def get_deadline_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_ORG_ADMIN_ONLY),
    org_id: int = Depends(get_current_org),
):
    """
    Deadline health: overdue, approaching, on-track, compliance trend.
    """
    return await org_analytics_service.get_deadline_health(db, org_id)
