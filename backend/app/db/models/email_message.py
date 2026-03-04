from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class EmailMessage(Base):
    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, index=True)
    email_config_id = Column(Integer, ForeignKey("email_configs.id"), nullable=True)
    message_id = Column(String, unique=True, nullable=False, index=True)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    received_date = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    email_config = relationship("EmailConfig", backref="messages")

    def __repr__(self):
        return f"<EmailMessage(from='{self.from_address}', subject='{self.subject}')>"
