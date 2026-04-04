"""Fix userrole enum to use lowercase values

Revision ID: 001_fix_userrole_enum
Revises: a9b8c7d6e5f4
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_fix_userrole_enum'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix userrole enum to use lowercase values."""
    # Drop any existing userrole enum (cascade to drop constraints)
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
    
    # Create the enum with lowercase values that match the Python UserRole enum
    op.execute("""
        CREATE TYPE userrole AS ENUM (
            'admin', 'org_admin', 'lawyer', 'assistant', 'viewer'
        )
    """)
    
    # Add role column to users if it doesn't exist
    op.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS role userrole NOT NULL DEFAULT 'lawyer'
    """)


def downgrade() -> None:
    """Downgrade: recreate old enum."""
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
