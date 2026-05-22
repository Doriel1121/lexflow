import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.models.document import document_tag_association


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    # name is no longer globally unique — uniqueness is enforced by the two
    # partial indexes below (one per org-scoped, one for global const tags).
    name = Column(String, nullable=False, index=True)
    # Semantic category:
    #   Global const  → case_type | document_type          (organization_id IS NULL)
    #   Org-scoped    → client_id | organization | project | ai_tag  (organization_id SET)
    category = Column(String, index=True, nullable=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )

    organization = relationship("Organization", backref="tags")
    documents = relationship(
        "Document", secondary=document_tag_association, back_populates="tags"
    )

    __table_args__ = (
        # Org-scoped uniqueness: no two tags in the same org can share a name.
        # Partial — only applies where organization_id IS NOT NULL.
        Index(
            "uq_tags_name_org",
            "name",
            "organization_id",
            unique=True,
            postgresql_where=sa.text("organization_id IS NOT NULL"),
        ),
        # Global const uniqueness: no two global tags can share (name, category).
        # Partial — only applies where organization_id IS NULL.
        Index(
            "uq_tags_global_name_category",
            "name",
            "category",
            unique=True,
            postgresql_where=sa.text("organization_id IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Tag(name='{self.name}', category='{self.category}', org={self.organization_id})>"
