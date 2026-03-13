import secrets
import re
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from app.db.base import Base


def _generate_slug(email_address: str) -> str:
    """Derive a URL-safe slug from an email address + random suffix."""
    local = email_address.split("@")[0]
    safe = re.sub(r"[^a-z0-9]", "-", local.lower())[:20].strip("-")
    suffix = secrets.token_hex(4)          # 8 hex chars → collision-resistant
    return f"{safe}-{suffix}"


def _generate_secret() -> str:
    return secrets.token_hex(32)           # 64-char HMAC signing secret


class EmailConfig(Base):
    __tablename__ = "email_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    # The email address this config is monitoring / representing
    email_address = Column(String, nullable=False)

    # ----------------------------------------------------------------
    # Inbound webhook approach — no IMAP / OAuth credentials needed
    # ----------------------------------------------------------------
    # Unique slug that forms the inbound address:
    #   <inbound_slug>@inbound.lexflow.app
    inbound_slug = Column(String(60), unique=True, nullable=True, index=True)

    # HMAC-SHA256 signing secret used to authenticate webhook POSTs
    webhook_secret = Column(String(64), nullable=True)

    # Feature flags
    is_active = Column(Boolean, default=True)
    ingestion_enabled = Column(Boolean, default=True)

    # Stats (updated by the webhook handler)
    total_ingested = Column(Integer, default=0)
    last_received_at = Column(DateTime, nullable=True)

    # Legacy / fallback fields (kept to avoid breaking existing rows)
    provider = Column(String, nullable=True)        # "inbound" | legacy "imap"
    imap_server = Column(String, nullable=True)
    imap_port = Column(Integer, default=993)
    username = Column(String, nullable=True)
    encrypted_password = Column(String, nullable=True)
    last_synced_at = Column(String, nullable=True)

    def __repr__(self):
        return f"<EmailConfig(email='{self.email_address}', slug='{self.inbound_slug}')>"
