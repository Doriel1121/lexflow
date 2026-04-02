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

    # ── Cases: lawyer assignment + priority ───────────────────────────────
    op.add_column('cases', sa.Column('assigned_lawyer_id', sa.Integer(), nullable=True))
    op.add_column('cases', sa.Column('priority', sa.String(), server_default='normal', nullable=False))
    op.add_column('cases', sa.Column('priority_score', sa.Float(), server_default='0.0', nullable=False))
    op.create_index(op.f('ix_cases_assigned_lawyer_id'), 'cases', ['assigned_lawyer_id'], unique=False)
    op.create_foreign_key(
        'fk_cases_assigned_lawyer_id',
        'cases', 'users',
        ['assigned_lawyer_id'], ['id'],
        ondelete='SET NULL'
    )

    # ── Deadlines: alert tracking ─────────────────────────────────────────
    op.add_column('deadlines', sa.Column('alert_sent_at', sa.DateTime(), nullable=True))

    # ── Document Metadata: classification + keywords ──────────────────────
    op.add_column('document_metadata', sa.Column('classification_category', sa.String(), nullable=True))
    op.add_column('document_metadata', sa.Column('extracted_keywords', sa.JSON(), nullable=True))

    # ── Case Events: new table ────────────────────────────────────────────
    op.create_table(
        'case_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_events_id'), 'case_events', ['id'], unique=False)
    op.create_index(op.f('ix_case_events_case_id'), 'case_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_events_organization_id'), 'case_events', ['organization_id'], unique=False)
    op.create_index(op.f('ix_case_events_user_id'), 'case_events', ['user_id'], unique=False)
    op.create_index(op.f('ix_case_events_event_type'), 'case_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_case_events_created_at'), 'case_events', ['created_at'], unique=False)


def downgrade() -> None:
    """Reverse all changes."""

    # ── Drop case_events ──────────────────────────────────────────────────
    op.drop_index(op.f('ix_case_events_created_at'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_event_type'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_user_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_organization_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_case_id'), table_name='case_events')
    op.drop_index(op.f('ix_case_events_id'), table_name='case_events')
    op.drop_table('case_events')

    # ── Revert document_metadata ──────────────────────────────────────────
    op.drop_column('document_metadata', 'extracted_keywords')
    op.drop_column('document_metadata', 'classification_category')

    # ── Revert deadlines ──────────────────────────────────────────────────
    op.drop_column('deadlines', 'alert_sent_at')

    # ── Revert cases ──────────────────────────────────────────────────────
    op.drop_constraint('fk_cases_assigned_lawyer_id', 'cases', type_='foreignkey')
    op.drop_index(op.f('ix_cases_assigned_lawyer_id'), table_name='cases')
    op.drop_column('cases', 'priority_score')
    op.drop_column('cases', 'priority')
    op.drop_column('cases', 'assigned_lawyer_id')
