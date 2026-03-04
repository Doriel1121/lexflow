from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AuditLogBase(BaseModel):
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None

class AuditLog(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
