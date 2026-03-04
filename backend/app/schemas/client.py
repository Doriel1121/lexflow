from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ClientBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    is_high_risk: bool = False
    risk_notes: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    name: Optional[str] = None

class ClientInDBBase(ClientBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Client(ClientInDBBase):
    pass

class ClientInDB(ClientInDBBase):
    pass
