"""
CaseEvent model — timeline events for case history.

Each event records a significant action on a case (document added, deadline
created, status change, lawyer assignment, etc.) for the timeline view.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base


class CaseEvent(Base):
    __tablename__ = "case_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    event_type = Column(String(50), nullable=False, index=True)
    # event_type values:
    #   document_added, deadline_created, deadline_completed,
    #   status_changed, lawyer_assigned, note_added, case_created

    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    case = relationship("Case", back_populates="events")
    user = relationship("User", backref="case_events")
    organization = relationship("Organization", backref="case_events")
