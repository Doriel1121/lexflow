"""add smart features columns and case_events table

Revision ID: f1a2b3c4d5e6
Revises: 69195e739525
Create Date: 2026-03-20 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '69195e739525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add smart features columns and create case_events table."""

    # Cases: lawyer assignment + priority
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS assigned_lawyer_id INTEGER")
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT 'normal' NOT NULL")
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS priority_score DOUBLE PRECISION DEFAULT 0.0 NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_assigned_lawyer_id ON cases (assigned_lawyer_id)")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_cases_assigned_lawyer_id'
            ) THEN
                ALTER TABLE cases
                ADD CONSTRAINT fk_cases_assigned_lawyer_id
                FOREIGN KEY (assigned_lawyer_id) REFERENCES users (id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # Deadlines: alert tracking
    op.execute("ALTER TABLE deadlines ADD COLUMN IF NOT EXISTS alert_sent_at TIMESTAMP WITHOUT TIME ZONE")

    # Document Metadata: classification + keywords
    op.execute("ALTER TABLE document_metadata ADD COLUMN IF NOT EXISTS classification_category VARCHAR")
    op.execute("ALTER TABLE document_metadata ADD COLUMN IF NOT EXISTS extracted_keywords JSON")

    # Case Events: new table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS case_events (
            id SERIAL NOT NULL,
            case_id INTEGER NOT NULL,
            organization_id INTEGER,
            user_id INTEGER,
            event_type VARCHAR(50) NOT NULL,
            description TEXT,
            metadata_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE,
            FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_id ON case_events (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_case_id ON case_events (case_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_organization_id ON case_events (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_user_id ON case_events (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_event_type ON case_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_case_events_created_at ON case_events (created_at)")


def downgrade() -> None:
    """Reverse all changes."""

    # Drop case_events
    op.drop_index(op.f('ix_case_events_created_at'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_event_type'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_user_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_organization_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_case_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_id'), table_name='case_events')
    op.drop_table('case_events')

    # Revert document_metadata
    op.drop_column('document_metadata', 'extracted_keywords')
    op.drop_column('document_metadata', 'classification_category')

    # Revert deadlines
    op.drop_column('deadlines', 'alert_sent_at')

    # Revert cases
    op.drop_constraint('fk_cases_assigned_lawyer_id', 'cases', type_='foreignkey')
    op.drop_index(op.f('ix_cases_assigned_lawyer_id'), table_name='cases')
    op.drop_column('cases', 'priority_score')
    op.drop_column('cases', 'priority')
    op.drop_column('cases', 'assigned_lawyer_id')
