from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.db.base import Base

class EmailConfig(Base):
    __tablename__ = "email_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    provider = Column(String, nullable=False) # imap, graph, gmail
    email_address = Column(String, nullable=False)
    
    # IMAP settings
    imap_server = Column(String, nullable=True)
    imap_port = Column(Integer, default=993)
    username = Column(String, nullable=True)
    encrypted_password = Column(String, nullable=True) # or refresh_token for OAuth
    
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(String, nullable=True) # ISO format

    def __repr__(self):
        return f"<EmailConfig(email='{self.email_address}', provider='{self.provider}')>"
