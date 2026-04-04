"""create_organisations_table

Phase 1 of multi-tenant SaaS refactor.
Introduces the Organisation model — the tenant root.
No existing tables are modified.

Revision ID: a1b2c3d4e5f6
Revises: d9e8f7a6b5c4
Create Date: 2026-02-20 15:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd9e8f7a6b5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create organisations table.

    Uses only plain sqlalchemy constructs (no dialect-specific types)
    so this migration is safe on both SQLite (dev) and PostgreSQL (prod).
    """
    op.create_table(
        'organisations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('plan', sa.String(), nullable=False, server_default='free'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_organisations_name'),
    )
    op.create_index(op.f('ix_organisations_id'), 'organisations', ['id'], unique=False)
    op.create_index(op.f('ix_organisations_name'), 'organisations', ['name'], unique=True)


def downgrade() -> None:
    """Drop organisations table — fully reversible."""
    op.drop_index(op.f('ix_organisations_name'), table_name='organisations')
    op.drop_index(op.f('ix_organisations_id'), table_name='organisations')
    op.drop_table('organisations')
