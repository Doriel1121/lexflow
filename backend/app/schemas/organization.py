from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class OrganizationBase(BaseModel):
    name: str
    ai_battery_save_mode: bool = False

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(OrganizationBase):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    ai_battery_save_mode: Optional[bool] = None

class OrganizationInDBBase(OrganizationBase):
    id: int
    slug: str
    is_active: bool
    ai_battery_save_mode: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Organization(OrganizationInDBBase):
    pass
