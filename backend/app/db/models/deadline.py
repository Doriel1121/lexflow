from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Enum,
    Boolean,
    JSON
)
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class DeadlineType(enum.Enum):
    HEARING = "hearing"
    FILING = "filing"
    RESPONSE = "response"
    APPEAL = "appeal"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"
    OTHER = "other"

class Deadline(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String, nullable=True) # For manual deadlines
    deadline_date = Column(DateTime, nullable=False)
    deadline_type = Column(Enum(DeadlineType), default=DeadlineType.OTHER, nullable=False)
    description = Column(String, nullable=True)
    confidence_score = Column(Float, default=1.0) # 1.0 for manual
    
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    alert_sent_at = Column(DateTime, nullable=True)  # tracks when alert notification was sent
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", backref="deadlines")
    case = relationship("Case", backref="deadlines")
    organization = relationship("Organization", backref="deadlines")
    assignee = relationship("User", foreign_keys=[assignee_id], backref="assigned_deadlines")
    creator = relationship("User", foreign_keys=[created_by_id], backref="created_deadlines")

    def __repr__(self):
        return f"<Deadline(date='{self.deadline_date}', type='{self.deadline_type.value}')>"
