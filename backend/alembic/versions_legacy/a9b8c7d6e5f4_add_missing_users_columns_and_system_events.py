"""add_missing_users_columns_and_system_events

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to users
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'lawyer'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_id VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_access_token VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_refresh_token VARCHAR")

    # Add missing columns to cases and documents if not present
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id)")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id)")

    # Create system_events table
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_events (
            id SERIAL NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            user_bucket VARCHAR(255),
            organization_id INTEGER,
            occurred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            metadata_json JSONB,
            PRIMARY KEY (id)
        )
    """)
    op.execute("ALTER TABLE system_events ADD COLUMN IF NOT EXISTS organization_id INTEGER")
    op.execute("ALTER TABLE system_events ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")
    op.execute("CREATE INDEX IF NOT EXISTS ix_system_events_occurred_at ON system_events (occurred_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_system_events_organization_id ON system_events (organization_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_events CASCADE")
