from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    contact_person = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_high_risk = Column(Boolean, default=False, nullable=False)
    risk_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship("Organization", backref="clients")

    def __repr__(self):
        return f"<Client(name='{self.name}')>"
