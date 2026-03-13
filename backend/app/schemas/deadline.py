from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.db.models.deadline import DeadlineType

class DeadlineBase(BaseModel):
    deadline_date: datetime
    deadline_type: DeadlineType
    title: Optional[str] = None
    description: Optional[str] = None
    confidence_score: float = 1.0
    assignee_id: Optional[int] = None
    is_completed: bool = False

class DeadlineCreate(DeadlineBase):
    document_id: Optional[int] = None
    case_id: Optional[int] = None
    organization_id: Optional[int] = None

class DeadlineUpdate(DeadlineBase):
    deadline_date: Optional[datetime] = None
    deadline_type: Optional[DeadlineType] = None
    completed_at: Optional[datetime] = None

class Deadline(DeadlineBase):
    id: int
    document_id: Optional[int] = None
    document_name: Optional[str] = None
    case_id: Optional[int] = None
    organization_id: Optional[int] = None
    created_by_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
