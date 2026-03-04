from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_
from datetime import datetime
from typing import Optional

from app.core.dependencies import get_db, RoleChecker, get_current_user
from app.db.models.user import User, UserRole
from app.db.models.organization import Organization
from app.db.models.document import Document
from app.db.models.case import Case
from app.db.models.tag import Tag
from app.schemas.admin import (
    UserStats, OrganizationStats, SubscriptionStats, 
    SystemHealthMetrics, AdminDashboard
)
from app.schemas.organization import OrganizationCreate
from app.schemas.user import UserCreate
from app.crud.organization import organization_crud
from app.crud.user import user_crud
from app.core.security import get_password_hash
import secrets

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboard)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Get complete backoffice dashboard with system-wide analytics.
    Only ADMIN users can access this.
    """
    
    # === USER STATISTICS ===
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).filter(User.is_active == True)
    )
    inactive_users = await db.scalar(
        select(func.count(User.id)).filter(User.is_active == False)
    )
    
    # Users by role
    users_by_role = {}
    for role in UserRole:
        count = await db.scalar(
            select(func.count(User.id)).filter(User.role == role)
        )
        users_by_role[role.value] = count or 0
    
    user_stats = UserStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        inactive_users=inactive_users or 0,
        users_by_role=users_by_role
    )
    
    # === ORGANIZATION STATISTICS ===
    total_orgs = await db.scalar(select(func.count(Organization.id)))
    active_orgs = await db.scalar(
        select(func.count(Organization.id)).filter(Organization.is_active == True)
    )
    inactive_orgs = await db.scalar(
        select(func.count(Organization.id)).filter(Organization.is_active == False)
    )
    
    # Total org members
    total_org_members = await db.scalar(
        select(func.count(User.id)).filter(User.organization_id != None)
    )
    
    avg_users_per_org = (total_org_members / max(total_orgs or 1, 1))
    
    org_stats = OrganizationStats(
        total_organizations=total_orgs or 0,
        active_organizations=active_orgs or 0,
        inactive_organizations=inactive_orgs or 0,
        avg_users_per_org=round(avg_users_per_org, 2),
        total_org_members=total_org_members or 0
    )
    
    # === SUBSCRIPTION STATISTICS (each org = 1 subscription) ===
    org_to_user_count = {}
    result = await db.execute(
        select(Organization.id, func.count(User.id).label('member_count'))
        .outerjoin(User, User.organization_id == Organization.id)
        .group_by(Organization.id)
    )
    for row in result:
        org_id, member_count = row
        org_to_user_count[str(org_id)] = member_count or 0
    
    subscription_stats = SubscriptionStats(
        total_subscriptions=total_orgs or 0,
        active_subscriptions=active_orgs or 0,
        org_id_to_user_count=org_to_user_count
    )
    
    # === SYSTEM HEALTH METRICS ===
    total_documents = await db.scalar(select(func.count(Document.id)))
    total_cases = await db.scalar(select(func.count(Case.id)))
    total_tags = await db.scalar(select(func.count(Tag.id)))
    
    # Documents by organization
    docs_by_org = {}
    result = await db.execute(
        select(Document.organization_id, func.count(Document.id).label('doc_count'))
        .group_by(Document.organization_id)
    )
    for row in result:
        org_id, count = row
        docs_by_org[str(org_id or "unassigned")] = count
    
    # Most active organizations (by member count and document count)
    result = await db.execute(
        select(
            Organization.id,
            Organization.name,
            func.count(User.id).label('member_count')
        )
        .outerjoin(User, User.organization_id == Organization.id)
        .group_by(Organization.id, Organization.name)
        .order_by(func.count(User.id).desc())
        .limit(10)
    )
    most_active_orgs = []
    for row in result:
        org_id, org_name, member_count = row
        doc_count = docs_by_org.get(str(org_id), 0)
        most_active_orgs.append({
            "org_id": org_id,
            "name": org_name,
            "member_count": member_count or 0,
            "document_count": doc_count
        })
    
    system_health = SystemHealthMetrics(
        total_documents=total_documents or 0,
        total_cases=total_cases or 0,
        total_tags=total_tags or 0,
        documents_by_organization=docs_by_org,
        most_active_orgs=most_active_orgs
    )
    
    # === SUMMARY For dashboard cards ===
    summary = {
        "total_users": total_users or 0,
        "total_orgs": total_orgs or 0,
        "total_documents": total_documents or 0,
        "total_cases": total_cases or 0,
        "avg_org_size": round(avg_users_per_org, 1),
        "active_subscriptions": active_orgs or 0,
    }
    
    return AdminDashboard(
        timestamp=datetime.utcnow(),
        user_stats=user_stats,
        organization_stats=org_stats,
        subscription_stats=subscription_stats,
        system_health=system_health,
        summary=summary
    )


@router.get("/users")
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
    skip: int = 0,
    limit: int = 100,
):
    """List all users in the system (admin only)"""
    result = await db.execute(
        select(User)
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if u.role else "unassigned",
            "organization_id": u.organization_id,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.get("/organizations")
async def list_all_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
    skip: int = 0,
    limit: int = 100,
):
    """List all organizations in the system (admin only)"""
    result = await db.execute(
        select(Organization)
        .offset(skip)
        .limit(limit)
    )
    orgs = result.scalars().all()
    
    # Get member count for each org
    org_ids = [org.id for org in orgs]
    member_counts = {}
    if org_ids:
        result = await db.execute(
            select(Organization.id, func.count(User.id).label('member_count'))
            .filter(Organization.id.in_(org_ids))
            .outerjoin(User, User.organization_id == Organization.id)
            .group_by(Organization.id)
        )
        for row in result:
            org_id, count = row
            member_counts[org_id] = count or 0
    
    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "is_active": o.is_active,
            "created_at": o.created_at,
            "member_count": member_counts.get(o.id, 0),
        }
        for o in orgs
    ]

from pydantic import BaseModel, EmailStr

class AdminProvisionRequest(BaseModel):
    organization_name: str
    admin_email: EmailStr
    admin_name: str
    password: Optional[str] = None

@router.post("/organizations")
async def provision_organization(
    provision_request: AdminProvisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Super Admin endpoint to manually create an organization and its first admin user.
    """
    # 1. Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=provision_request.admin_email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists.")
        
    # 2. Create Org
    org_in = OrganizationCreate(name=provision_request.organization_name)
    org = await organization_crud.create(db, obj_in=org_in)
    
    # 3. Create Admin User
    initial_password = provision_request.password or secrets.token_urlsafe(12)
    new_user = UserCreate(
        email=provision_request.admin_email,
        password=initial_password,
        full_name=provision_request.admin_name,
        role=UserRole.ORG_ADMIN
    )
    
    user = await user_crud.create(db, user_in=new_user, organization_id=org.id)
    
    return {
        "message": "Organization provisioned successfully",
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug
        },
        "admin_user": {
            "id": user.id,
            "email": user.email,
            "temporary_password": initial_password if not provision_request.password else "Provided by admin"
        }
    }


@router.get("/organizations/{org_id}/details")
async def get_organization_details(
    org_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
):
    """Get detailed analytics for a specific organization"""
    
    # Get org
    org = await db.scalar(select(Organization).filter(Organization.id == org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Member count by role
    result = await db.execute(
        select(User.role, func.count(User.id).label('count'))
        .filter(User.organization_id == org_id)
        .group_by(User.role)
    )
    members_by_role = {row[0].value if row[0] else "unassigned": row[1] for row in result}
    
    # Document count
    doc_count = await db.scalar(
        select(func.count(Document.id)).filter(Document.organization_id == org_id)
    )
    
    # Case count
    case_count = await db.scalar(
        select(func.count(Case.id)).filter(Case.organization_id == org_id)
    )
    
    # Total members
    total_members = await db.scalar(
        select(func.count(User.id)).filter(User.organization_id == org_id)
    )
    
    return {
        "organization": {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "created_at": org.created_at,
            "is_active": org.is_active,
        },
        "stats": {
            "total_members": total_members or 0,
            "members_by_role": members_by_role,
            "documents": doc_count or 0,
            "cases": case_count or 0,
        }
    }


@router.get("/system-stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
):
    """Quick system statistics endpoint"""
    
    total_users = await db.scalar(select(func.count(User.id)))
    total_orgs = await db.scalar(select(func.count(Organization.id)))
    total_docs = await db.scalar(select(func.count(Document.id)))
    total_cases = await db.scalar(select(func.count(Case.id)))
    
    return {
        "total_users": total_users or 0,
        "total_organizations": total_orgs or 0,
        "total_documents": total_docs or 0,
        "total_cases": total_cases or 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN])),
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    action: Optional[str] = None
):
    """Get system audit logs (Admin only)"""
    from app.db.models.audit_log import AuditLog
    
    query = select(AuditLog)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
        
    query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp,
            "user_id": log.user_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address
        }
        for log in logs
    ]
