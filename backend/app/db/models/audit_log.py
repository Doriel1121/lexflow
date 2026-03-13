from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    event_type = Column(String(100), nullable=False, index=True) # Was 'action'
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True) # Allow string UUIDs or Ints
    
    http_method = Column(String(10), nullable=True)
    path = Column(String(255), nullable=True)
    status_code = Column(Integer, nullable=True)
    
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    metadata_json = Column(JSONB, nullable=True) # Was 'details'
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    previous_hash = Column(String(64), nullable=True, index=True)
    hash = Column(String(64), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
    # organization = relationship("Organization") # Assuming this exists or can be inferred

