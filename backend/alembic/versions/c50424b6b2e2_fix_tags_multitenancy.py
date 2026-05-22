"""fix_tags_multitenancy

Revision ID: c50424b6b2e2
Revises: 317988fe2f1f
Create Date: 2026-05-01 00:00:00.000000

Changes
-------
1. Deduplicate existing tag rows that would violate the new constraints.
   - For org-scoped categories (client_id, organization, project, ai_tag):
     keep the lowest-id row per (name, organization_id), reassign all
     document_tag_association rows to the survivor, delete duplicates.
   - For global const categories (case_type, document_type, NULL org):
     keep the lowest-id row per (name, category) where org IS NULL,
     reassign associations, delete duplicates.

2. Drop the old global unique index on tags.name.

3. Recreate tags.name as a plain (non-unique) index.

4. Add UNIQUE(name, organization_id) for org-scoped rows
   (enforced only where organization_id IS NOT NULL via partial index).

5. Add UNIQUE(name, category) for global const rows
   (enforced only where organization_id IS NULL via partial index).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "c50424b6b2e2"
down_revision: Union[str, Sequence[str], None] = "317988fe2f1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Categories that are org-scoped (contain real client data)
ORG_SCOPED_CATEGORIES = ("client_id", "organization", "project", "ai_tag")

# Categories that are global constants (semantic, shareable)
GLOBAL_CATEGORIES = ("case_type", "document_type")


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1a. Deduplicate org-scoped tags: keep lowest id per (name, org_id)
    # ------------------------------------------------------------------
    conn.execute(text("""
        WITH dupes AS (
            SELECT
                id,
                name,
                organization_id,
                MIN(id) OVER (PARTITION BY name, organization_id) AS keep_id
            FROM tags
            WHERE organization_id IS NOT NULL
        ),
        to_reassign AS (
            SELECT id AS old_id, keep_id AS new_id
            FROM dupes
            WHERE id <> keep_id
        )
        UPDATE document_tag_association dta
        SET tag_id = tr.new_id
        FROM to_reassign tr
        WHERE dta.tag_id = tr.old_id
          AND NOT EXISTS (
              SELECT 1 FROM document_tag_association
              WHERE document_id = dta.document_id AND tag_id = tr.new_id
          )
    """))

    conn.execute(text("""
        DELETE FROM document_tag_association
        WHERE tag_id IN (
            SELECT id FROM (
                SELECT id, MIN(id) OVER (PARTITION BY name, organization_id) AS keep_id
                FROM tags
                WHERE organization_id IS NOT NULL
            ) sub
            WHERE id <> keep_id
        )
    """))

    conn.execute(text("""
        DELETE FROM tags
        WHERE organization_id IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM tags
              WHERE organization_id IS NOT NULL
              GROUP BY name, organization_id
          )
    """))

    # ------------------------------------------------------------------
    # 1b. Deduplicate global const tags: keep lowest id per (name, category)
    # ------------------------------------------------------------------
    conn.execute(text("""
        WITH dupes AS (
            SELECT
                id,
                name,
                category,
                MIN(id) OVER (PARTITION BY name, category) AS keep_id
            FROM tags
            WHERE organization_id IS NULL
        ),
        to_reassign AS (
            SELECT id AS old_id, keep_id AS new_id
            FROM dupes
            WHERE id <> keep_id
        )
        UPDATE document_tag_association dta
        SET tag_id = tr.new_id
        FROM to_reassign tr
        WHERE dta.tag_id = tr.old_id
          AND NOT EXISTS (
              SELECT 1 FROM document_tag_association
              WHERE document_id = dta.document_id AND tag_id = tr.new_id
          )
    """))

    conn.execute(text("""
        DELETE FROM document_tag_association
        WHERE tag_id IN (
            SELECT id FROM (
                SELECT id, MIN(id) OVER (PARTITION BY name, category) AS keep_id
                FROM tags
                WHERE organization_id IS NULL
            ) sub
            WHERE id <> keep_id
        )
    """))

    conn.execute(text("""
        DELETE FROM tags
        WHERE organization_id IS NULL
          AND id NOT IN (
              SELECT MIN(id)
              FROM tags
              WHERE organization_id IS NULL
              GROUP BY name, category
          )
    """))

    # ------------------------------------------------------------------
    # 2. Drop the old global unique index on name
    # ------------------------------------------------------------------
    op.drop_index("ix_tags_name", table_name="tags")

    # ------------------------------------------------------------------
    # 3. Recreate name as a plain (non-unique) index
    # ------------------------------------------------------------------
    op.create_index("ix_tags_name", "tags", ["name"], unique=False)

    # ------------------------------------------------------------------
    # 4. Partial unique index for org-scoped tags: UNIQUE(name, org_id)
    #    Only enforced where organization_id IS NOT NULL
    # ------------------------------------------------------------------
    op.execute(
        "CREATE UNIQUE INDEX uq_tags_name_org "
        "ON tags (name, organization_id) "
        "WHERE organization_id IS NOT NULL"
    )

    # ------------------------------------------------------------------
    # 5. Partial unique index for global const tags: UNIQUE(name, category)
    #    Only enforced where organization_id IS NULL
    # ------------------------------------------------------------------
    op.execute(
        "CREATE UNIQUE INDEX uq_tags_global_name_category "
        "ON tags (name, category) "
        "WHERE organization_id IS NULL"
    )


def downgrade() -> None:
    # Remove new indexes
    op.execute("DROP INDEX IF EXISTS uq_tags_name_org")
    op.execute("DROP INDEX IF EXISTS uq_tags_global_name_category")

    # Remove plain name index
    op.drop_index("ix_tags_name", table_name="tags")

    # Restore original global unique index
    # NOTE: this will fail if duplicate names exist across orgs.
    # Run deduplication manually before downgrading in production.
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)
