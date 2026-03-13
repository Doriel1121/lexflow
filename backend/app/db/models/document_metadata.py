from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
# from sqlalchemy import ARRAY # Removed
# from sqlalchemy.dialects.postgresql import JSONB # Removed for SQLite compatibility
from sqlalchemy.orm import relationship
from app.db.base import Base

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    dates = Column(JSON, nullable=True)  # List of extracted dates
    entities = Column(JSON, nullable=True)  # Person/Organization names
    amounts = Column(JSON, nullable=True)  # Monetary amounts
    case_numbers = Column(JSON, nullable=True)  # Possible case numbers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="document_metadata")

    def __repr__(self):
        return f"<DocumentMetadata(document_id={self.document_id})>"
