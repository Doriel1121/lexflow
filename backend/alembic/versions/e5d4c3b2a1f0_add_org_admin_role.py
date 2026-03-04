"""add_org_admin_role

Revision ID: e5d4c3b2a1f0
Revises: d9e8f7a6b5c4
Create Date: 2026-02-28 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5d4c3b2a1f0'
down_revision: Union[str, Sequence[str], None] = 'd9e8f7a6b5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ORG_ADMIN to userrole enum."""
    # PostgreSQL enum alteration: add new value
    op.execute("ALTER TYPE userrole ADD VALUE 'org_admin' BEFORE 'admin'")


def downgrade() -> None:
    """Remove ORG_ADMIN from userrole enum."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This is a limitation of PostgreSQL enums
    # In practice, you would need to recreate the type
    raise NotImplementedError("Cannot downgrade enum value in PostgreSQL")
