from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.dependencies import get_db, get_current_active_user
from app.db.models.user import User as DBUser, UserRole
from app.db.models.deadline import Deadline as DBDeadline, DeadlineType
from app.db.models.case import Case as DBCase
from app.schemas.deadline import Deadline, DeadlineCreate, DeadlineUpdate
from app.services.audit import log_audit
from app.services.audit import log_audit # Already imported but being safe
from app.crud.crud_notification import notification_crud
from app.schemas.notification import NotificationCreate

router = APIRouter()

@router.post("/", response_model=Deadline)
async def create_deadline(
    *,
    db: AsyncSession = Depends(get_db),
    deadline_in: DeadlineCreate,
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Create new deadline.
    """
    db_obj = DBDeadline(
        **deadline_in.model_dump(exclude_unset=True),
        created_by_id=current_user.id,
        organization_id=current_user.organization_id
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    
    # Notify assignee if exists
    if db_obj.assignee_id:
        await notification_crud.create_notification(
            db,
            notification_in=NotificationCreate(
                title="New Deadline Assigned",
                message=f"You have been assigned a new deadline: {db_obj.title or db_obj.deadline_type.value}",
                type="deadline",
                user_id=db_obj.assignee_id,
                organization_id=current_user.organization_id,
                link=f"/cases/{db_obj.case_id}" if db_obj.case_id else None
            )
        )
    
    await log_audit(
        db,
        action="create_deadline",
        entity_type="deadline",
        entity_id=db_obj.id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        details={"title": db_obj.title, "date": str(db_obj.deadline_date)}
    )
    
    return db_obj

@router.patch("/{deadline_id}", response_model=Deadline)
async def update_deadline(
    *,
    db: AsyncSession = Depends(get_db),
    deadline_id: int,
    deadline_in: DeadlineUpdate,
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Update a deadline.
    """
    result = await db.execute(select(DBDeadline).filter(DBDeadline.id == deadline_id))
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Deadline not found")
    
    # Check org access
    if db_obj.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_data = deadline_in.model_dump(exclude_unset=True)
    
    # Special handling for completion
    if "is_completed" in update_data:
        if update_data["is_completed"] and not db_obj.is_completed:
            db_obj.completed_at = datetime.utcnow()
        elif not update_data["is_completed"]:
            db_obj.completed_at = None

    # Track assignee change for notification
    old_assignee = db_obj.assignee_id
    
    for field in update_data:
        setattr(db_obj, field, update_data[field])
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    
    # Notify new assignee
    if db_obj.assignee_id and db_obj.assignee_id != old_assignee:
        await notification_crud.create_notification(
            db,
            notification_in=NotificationCreate(
                title="Deadline Reassigned",
                message=f"A deadline has been reassigned to you: {db_obj.title or db_obj.deadline_type.value}",
                type="deadline",
                user_id=db_obj.assignee_id,
                organization_id=current_user.organization_id,
                link=f"/cases/{db_obj.case_id}" if db_obj.case_id else None
            )
        )

    await log_audit(
        db,
        action="update_deadline",
        entity_type="deadline",
        entity_id=db_obj.id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        details={"changes": update_data}
    )
    
    return db_obj

@router.delete("/{deadline_id}", response_model=dict)
async def delete_deadline(
    *,
    db: AsyncSession = Depends(get_db),
    deadline_id: int,
    current_user: DBUser = Depends(get_current_active_user),
) -> Any:
    """
    Delete a deadline.
    """
    result = await db.execute(select(DBDeadline).filter(DBDeadline.id == deadline_id))
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Deadline not found")
    
    if db_obj.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    await db.delete(db_obj)
    await db.commit()
    
    return {"message": "Deadline deleted successfully"}
