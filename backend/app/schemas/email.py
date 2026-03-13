from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class EmailConfigCreate(BaseModel):
    email_address: str
    # All IMAP fields are now optional — we don't need them for inbound webhook
    provider: Optional[str] = "inbound"
    imap_server: Optional[str] = None
    imap_port: Optional[int] = 993
    username: Optional[str] = None
    password: Optional[str] = None


class EmailConfigResponse(BaseModel):
    id: int
    email_address: str
    provider: Optional[str] = "inbound"
    is_active: bool
    ingestion_enabled: Optional[bool] = True
    inbound_slug: Optional[str] = None
    total_ingested: Optional[int] = 0
    last_received_at: Optional[datetime] = None
    last_synced_at: Optional[str] = None

    # Computed property — returned as a convenience field
    @property
    def inbound_address(self) -> Optional[str]:
        if self.inbound_slug:
            return f"{self.inbound_slug}@inbound.lexflow.app"
        return None

    class Config:
        from_attributes = True
