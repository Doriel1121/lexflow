from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, String, JSON

from app.db.base import Base


class DocumentProcessingLog(Base):
    __tablename__ = "document_processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    stage = Column(String(64), nullable=True)
    event_type = Column(String(32), nullable=False, default="error")
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

