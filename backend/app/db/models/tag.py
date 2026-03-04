from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.models.document import document_tag_association

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    category = Column(String, index=True, nullable=True) # e.g. 'project', 'client_id', 'general'
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)

    organization = relationship("Organization", backref="tags")
    documents = relationship("Document", secondary=document_tag_association, back_populates="tags")

    def __repr__(self):
        return f"<Tag(name='{self.name}')>"
