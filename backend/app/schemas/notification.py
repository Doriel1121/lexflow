from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    link: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None

class NotificationCreate(NotificationBase):
    user_id: int
    organization_id: int

class NotificationUpdate(BaseModel):
    read: bool

class NotificationOut(NotificationBase):
    id: int
    user_id: int
    organization_id: int
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True
