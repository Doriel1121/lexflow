from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class EmailConfigCreate(BaseModel):
    email_address: str
    provider: str
    imap_server: Optional[str] = None
    imap_port: Optional[int] = 993
    username: Optional[str] = None
    password: Optional[str] = None

class EmailConfigResponse(BaseModel):
    id: int
    email_address: str
    provider: str
    is_active: bool
    last_synced_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
