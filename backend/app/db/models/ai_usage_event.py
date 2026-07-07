from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, String, Text, ForeignKey, Index

from app.db.base import Base


class AIUsageEvent(Base):
    """Per-call AI telemetry without storing prompt/output content."""

    __tablename__ = "ai_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    latency_ms = Column(Integer, nullable=True)
    input_chars = Column(Integer, nullable=True)
    output_chars = Column(Integer, nullable=True)
    estimated_input_tokens = Column(Integer, nullable=True)
    estimated_output_tokens = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_ai_usage_events_created_task", "created_at", "task_type"),
        Index("ix_ai_usage_events_org_created", "organization_id", "created_at"),
    )
