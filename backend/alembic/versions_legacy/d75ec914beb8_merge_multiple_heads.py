"""merge multiple heads

Revision ID: d75ec914beb8
Revises: b6221b46ff22, e5d4c3b2a1f0
Create Date: 2026-02-28 19:03:57.093084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd75ec914beb8'
down_revision: Union[str, Sequence[str], None] = ('b6221b46ff22', 'e5d4c3b2a1f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
