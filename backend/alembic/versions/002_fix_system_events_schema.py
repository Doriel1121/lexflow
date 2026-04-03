"""Fix system_events table schema to match Python model

Revision ID: 002_fix_system_events_schema
Revises: 001_fix_userrole_enum
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_fix_system_events_schema'
down_revision: Union[str, Sequence[str], None] = '001_fix_userrole_enum'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to system_events table
    op.execute("""
        ALTER TABLE system_events
        ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT NULL,
        ADD COLUMN IF NOT EXISTS latency_ms INTEGER DEFAULT NULL,
        ADD COLUMN IF NOT EXISTS feature VARCHAR(100) DEFAULT NULL,
        ADD COLUMN IF NOT EXISTS org_bucket INTEGER DEFAULT NULL
    """)
    
    # Rename metadata_json to extra (or add extra if metadata_json doesn't exist)
    # First check if metadata_json exists, if so we can leave it or migrate it
    # For now, just ensure extra column exists for forward compatibility
    op.execute("""
        ALTER TABLE system_events
        ADD COLUMN IF NOT EXISTS extra TEXT DEFAULT NULL
    """)


def downgrade() -> None:
    # Remove added columns
    op.execute("""
        ALTER TABLE system_events
        DROP COLUMN IF EXISTS status,
        DROP COLUMN IF EXISTS latency_ms,
        DROP COLUMN IF EXISTS feature,
        DROP COLUMN IF EXISTS org_bucket,
        DROP COLUMN IF EXISTS extra
    """)
