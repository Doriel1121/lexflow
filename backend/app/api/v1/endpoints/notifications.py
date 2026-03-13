from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.db.session import get_db
from app.crud.crud_notification import notification_crud
from app.schemas.notification import NotificationCreate, NotificationOut
from app.db.models.user import User

router = APIRouter()

@router.get("/", response_model=List[NotificationOut])
async def read_notifications(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve user notifications.
    """
    notifications = await notification_crud.get_multi_by_user(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return notifications

@router.get("/unread-count", response_model=int)
async def read_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get unread notification count.
    """
    count = await notification_crud.get_unread_count_by_user(db=db, user_id=current_user.id)
    return count

@router.post("/", response_model=NotificationOut)
async def create_notification(
    *,
    db: AsyncSession = Depends(get_db),
    notification_in: NotificationCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new notification.
    """
    # Normally this would be internal, but for testing purposes we can expose it
    # We might want to restrict this to system/admin or internal functions in production
    notification = await notification_crud.create(db=db, obj_in=notification_in)
    
    # Broadcast to WebSocket
    from app.api.ws.notifications import notification_manager
    await notification_manager.broadcast_to_user(
        user_id=notification_in.user_id,
        message={
            "type": "new_notification",
            "data": {
                "id": notification.id,
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "link": notification.link,
                "source_type": notification.source_type,
                "source_id": notification.source_id,
                "read": notification.read,
                "created_at": notification.created_at.isoformat() if notification.created_at else None
            }
        }
    )
    
    return notification

@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    *,
    db: AsyncSession = Depends(get_db),
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Mark a specific notification as read.
    """
    notification = await notification_crud.get(db=db, id=notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    notification = await notification_crud.mark_as_read(db=db, db_obj=notification)
    return notification

@router.patch("/read-all", response_model=dict)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Mark all notifications for the current user as read.
    """
    updated_count = await notification_crud.mark_all_as_read(db=db, user_id=current_user.id)
    return {"updated": updated_count}
