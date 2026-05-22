"""fix_tags_indexes_after_stamp

Revision ID: 7e2a2f9a6b3a
Revises: c50424b6b2e2
Create Date: 2026-05-15

This migration is defensive: some environments were "stamped" to
`c50424b6b2e2` without actually executing the index changes (notably dropping
the old globally-unique `ix_tags_name`). That breaks Smart Collections/tagging
because org-scoped tags (e.g. client IDs) must be allowed to repeat across
organizations.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "7e2a2f9a6b3a"
down_revision: Union[str, Sequence[str], None] = "c50424b6b2e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Ensure ix_tags_name is NOT unique
    op.execute("DROP INDEX IF EXISTS ix_tags_name")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tags_name ON tags (name)")

    # 2) Ensure partial unique indexes exist
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_name_org "
        "ON tags (name, organization_id) "
        "WHERE organization_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_global_name_category "
        "ON tags (name, category) "
        "WHERE organization_id IS NULL"
    )


def downgrade() -> None:
    # Best-effort revert to a globally unique name index.
    op.execute("DROP INDEX IF EXISTS uq_tags_name_org")
    op.execute("DROP INDEX IF EXISTS uq_tags_global_name_category")
    op.execute("DROP INDEX IF EXISTS ix_tags_name")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_tags_name ON tags (name)")

