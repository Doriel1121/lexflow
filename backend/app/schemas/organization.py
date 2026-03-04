from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class OrganizationBase(BaseModel):
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(OrganizationBase):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class OrganizationInDBBase(OrganizationBase):
    id: int
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Organization(OrganizationInDBBase):
    pass
