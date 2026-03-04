from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class CaseStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(CaseStatus), default=CaseStatus.OPEN, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", backref="cases")
    created_by = relationship("User", backref="created_cases")
    organization = relationship("Organization", backref="cases")
    notes = relationship("CaseNote", back_populates="case", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Case(title='{self.title}', status='{self.status.value}')>"

class CaseNote(Base):
    __tablename__ = "case_notes"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="notes")
    user = relationship("User", backref="case_notes")
    organization = relationship("Organization", backref="case_notes")

    def __repr__(self):
        return f"<CaseNote(case_id={self.case_id}, user_id={self.user_id})>"
