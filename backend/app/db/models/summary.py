from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    key_dates = Column(JSON, nullable=True)
    parties = Column(JSON, nullable=True)
    missing_documents_suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="summary")
    organization = relationship("Organization", backref="summaries")

    def __repr__(self):
        return f"<Summary(document_id={self.document_id})>"
