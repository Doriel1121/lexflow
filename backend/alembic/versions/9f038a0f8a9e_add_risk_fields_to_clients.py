"""Add risk fields to clients

Revision ID: 9f038a0f8a9e
Revises: 05da289d0c85
Create Date: 2026-03-02 18:23:40.854675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f038a0f8a9e'
down_revision: Union[str, Sequence[str], None] = '05da289d0c85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('is_high_risk', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('clients', sa.Column('risk_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'risk_notes')
    op.drop_column('clients', 'is_high_risk')
