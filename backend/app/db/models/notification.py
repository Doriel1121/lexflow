from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True) # e.g., 'deadline', 'document_uploaded', 'mention'
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    link = Column(String, nullable=True)
    source_type = Column(String, nullable=True) # e.g., 'case', 'document'
    source_id = Column(Integer, nullable=True)
    read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="notifications")
    organization = relationship("Organization", back_populates="notifications")
