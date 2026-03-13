"""
Organization Management Endpoints
Allows organization admins to manage members and roles
"""
from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.dependencies import get_db, get_current_active_user, RoleChecker
from app.db.models.user import User as DBUser, UserRole
from app.db.models.organization import Organization as DBOrganization

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/{org_id}/members", response_model=List[dict])
async def list_org_members(
    org_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    List all members of an organization.
    Org admins can only view their own organization.
    System admins can view any organization.
    """
    # Check authorization
    if current_user.role == UserRole.ORG_ADMIN:
        if current_user.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage your own organization"
            )
    elif current_user.role not in [UserRole.ADMIN, UserRole.LAWYER, UserRole.ASSISTANT]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view organization members"
        )
    
    # Get organization
    org = await db.get(DBOrganization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    
    # List members
    result = await db.execute(
        select(DBUser).filter(DBUser.organization_id == org_id)
    )
    members = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "email": m.email,
            "full_name": m.full_name,
            "role": m.role.value if m.role else "unassigned",
            "is_active": m.is_active,
            "is_org_admin": m.role == UserRole.ORG_ADMIN,
        }
        for m in members
    ]


@router.put("/{org_id}/members/{user_id}/role", response_model=dict)
async def update_member_role(
    org_id: int,
    user_id: int,
    new_role: str,  # "lawyer", "assistant", "viewer", "org_admin"
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN])),
):
    """
    Update a member's role within an organization.
    Only org admins (for their org) and system admins can do this.
    """
    # Validate new role
    try:
        role_enum = UserRole(new_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join([r.value for r in UserRole])}"
        )
    
    # System admins can't assign ADMIN role via this endpoint (security)
    if role_enum == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use system admin endpoints to assign ADMIN role"
        )
    
    # Check authorization: org admins can only manage their own org
    if current_user.role == UserRole.ORG_ADMIN:
        if current_user.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage your own organization"
            )
    
    # Get the user to update
    user = await db.get(DBUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Verify user belongs to this organization
    if user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this organization"
        )
    
    # Prevent removing yourself as org admin (if you're the only one)
    if current_user.id == user_id and current_user.role == UserRole.ORG_ADMIN and role_enum != UserRole.ORG_ADMIN:
        # Check if there's another org admin
        result = await db.execute(
            select(DBUser).filter(
                DBUser.organization_id == org_id,
                DBUser.role == UserRole.ORG_ADMIN,
                DBUser.id != user_id
            )
        )
        other_admins = result.scalars().all()
        if not other_admins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove the last organization admin. Assign another org admin first."
            )
    
    # Update role
    old_role = user.role
    user.role = role_enum
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "old_role": old_role.value if old_role else None,
        "new_role": role_enum.value,
        "message": f"Updated {user.email} from {old_role.value if old_role else 'unassigned'} to {role_enum.value}"
    }


@router.post("/{org_id}/members/{user_id}/deactivate", response_model=dict)
async def deactivate_member(
    org_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN])),
):
    """
    Deactivate a member within an organization.
    Organization admins can only deactivate members from their org.
    """
    # Check authorization
    if current_user.role == UserRole.ORG_ADMIN:
        if current_user.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only manage your own organization"
            )
    
    # Get user
    user = await db.get(DBUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Verify user belongs to this organization
    if user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this organization"
        )
    
    # Prevent deactivating yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate your own account"
        )
    
    # Deactivate
    user.is_active = False
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": f"Deactivated {user.email}"
    }


@router.get("/audit-logs", response_model=dict)
async def get_org_audit_logs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ORG_ADMIN])),
):
    """
    Get organization audit logs securely.
    ORGs only see their own logs.
    """
    from app.db.models.audit_log import AuditLog
    
    if limit > 500:
        limit = 500
        
    query = select(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id
    ).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    count_query = select(func.count(AuditLog.id)).filter(
        AuditLog.organization_id == current_user.organization_id
    )
    total_count = await db.scalar(count_query)
    
    return {
        "items": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "user_id": log.user_id,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "http_method": log.http_method,
                "path": log.path,
                "status_code": log.status_code,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat(),
                "hash": log.hash,
                "previous_hash": log.previous_hash
            } for log in logs
        ],
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


@router.get("/{org_id}", response_model=dict)
async def get_org_details(
    org_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Get organization details.
    Org members can view their own org; system admins can view any.
    """
    org = await db.get(DBOrganization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    
    # Check authorization
    if current_user.organization_id != org_id and current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this organization"
        )
    
    # Count members by role
    result = await db.execute(
        select(DBUser.role, func.count(DBUser.id)).filter(
            DBUser.organization_id == org_id
        ).group_by(DBUser.role)
    )
    role_counts = {role: count for role, count in result.all()}
    
    return {
        "id": org.id,
        "name": org.name,
        "ai_battery_save_mode": org.ai_battery_save_mode,
        "created_at": org.created_at,
        "member_count": sum(role_counts.values()),
        "role_distribution": {role.value if role else "unassigned": count for role, count in role_counts.items()},
    }

@router.patch("/{org_id}/settings", response_model=dict)
async def update_org_settings(
    org_id: int,
    settings_update: dict,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Update organization-wide settings.
    RESTRICTED: Only System Admins (ADMIN) can change these settings.
    """
    org = await db.get(DBOrganization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    
    # Update fields
    if "ai_battery_save_mode" in settings_update:
        org.ai_battery_save_mode = settings_update["ai_battery_save_mode"]
    
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    return {
        "id": org.id,
        "name": org.name,
        "ai_battery_save_mode": org.ai_battery_save_mode,
        "message": "Organization settings updated successfully"
    }
