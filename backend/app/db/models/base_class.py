from app.db.base import Base
from app.db.models.organization import Organization  # Phase 1 — tenant root (must be first)
from app.db.models.user import User
from app.db.models.client import Client
from app.db.models.case import Case, CaseNote
from app.db.models.document import Document
from app.db.models.tag import Tag
from app.db.models.summary import Summary
from app.db.models.audit_log import AuditLog
from app.db.models.document_metadata import DocumentMetadata

# This file imports all models so they are registered with SQLAlchemy's
# declarative Base.metadata. This enables Alembic autogenerate and string-based
# relationship() resolution to work correctly.
