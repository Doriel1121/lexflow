from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator
from app.db.models.case import CaseStatus

class CaseNoteBase(BaseModel):
    content: str

class CaseNoteCreate(CaseNoteBase):
    pass

class CaseNoteUpdate(CaseNoteBase):
    pass

class CaseNote(CaseNoteBase):
    id: int
    case_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CaseBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "OPEN"

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if isinstance(v, str):
            valid_statuses = ['OPEN', 'CLOSED', 'PENDING']
            if v.upper() not in valid_statuses:
                raise ValueError(f'Status must be one of: {valid_statuses}')
            return v.upper()
        return v

class CaseCreate(CaseBase):
    client_id: Optional[int] = None

class CaseUpdate(CaseBase):
    title: Optional[str] = None
    client_id: Optional[int] = None
    status: Optional[str] = None

class Case(CaseBase):
    id: int
    client_id: Optional[int] = None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    notes: List[CaseNote] = []
    documents: Optional[List[dict]] = []

    class Config:
        from_attributes = True
