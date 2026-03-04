from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Import all models to ensure they're registered
from app.db.models.organization import Organization  # noqa: F401
from app.db.models.user import User  # noqa: F401
from app.db.models.client import Client  # noqa: F401
from app.db.models.case import Case, CaseNote  # noqa: F401
from app.db.models.document import Document  # noqa: F401
from app.db.models.tag import Tag  # noqa: F401
from app.db.models.summary import Summary  # noqa: F401
from app.db.models.audit_log import AuditLog  # noqa: F401
from app.db.models.notification import Notification  # noqa: F401
