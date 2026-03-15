from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, Text, ForeignKey, String

from app.db.base import Base


class DocumentProcessingLog(Base):
    __tablename__ = "document_processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

