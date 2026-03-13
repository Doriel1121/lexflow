from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AuditLogBase(BaseModel):
    event_type: str
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    http_method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLog(AuditLogBase):
    id: int
    timestamp: datetime
    previous_hash: Optional[str] = None
    hash: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

