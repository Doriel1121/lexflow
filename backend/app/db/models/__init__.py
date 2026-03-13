"""
Importing `base_class` ensures all model modules are imported and
registered with SQLAlchemy's declarative base. This lets relationship()
lookups (by string name) resolve during mapper configuration.
"""

from .base_class import *  # noqa: F401,F403
from .organization import Organization
from .user import User
from .client import Client
from .case import Case, CaseNote
from .document import Document
from .tag import Tag
from .summary import Summary
from .audit_log import AuditLog
from .notification import Notification
from .deadline import Deadline, DeadlineType
from .email_config import EmailConfig
from .email_message import EmailMessage
