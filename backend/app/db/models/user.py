from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"              # System-wide administrator
    ORG_ADMIN = "org_admin"      # Organization administrator (manages org members)
    LAWYER = "lawyer"            # Organization member with write access
    ASSISTANT = "assistant"      # Organization member with write access
    VIEWER = "viewer"            # Organization member with read-only access

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Multi-tenant
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", backref="users")
    
    # OAuth specific fields
    social_id = Column(String, nullable=True)
    provider = Column(String, nullable=True) # google, microsoft
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    
    # RBAC
    role = Column(Enum(UserRole), default=UserRole.LAWYER, nullable=False)

    # Audit Logs
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(email='{self.email}')>"
