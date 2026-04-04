"""fix system metrics id defaults

Revision ID: 004_fix_metrics_id
Revises: 003_add_system_analytics_tables
Create Date: 2026-04-03 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '004_fix_metrics_id'
down_revision: Union[str, Sequence[str], None] = '003_add_system_analytics_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure id columns have sequences/defaults for inserts
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'system_metrics_daily'
                  AND column_name = 'id'
                  AND column_default LIKE 'nextval%'
            ) THEN
                CREATE SEQUENCE IF NOT EXISTS system_metrics_daily_id_seq;
                ALTER TABLE system_metrics_daily
                    ALTER COLUMN id SET DEFAULT nextval('system_metrics_daily_id_seq');
                ALTER SEQUENCE system_metrics_daily_id_seq
                    OWNED BY system_metrics_daily.id;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenant_cohorts'
                  AND column_name = 'id'
                  AND column_default LIKE 'nextval%'
            ) THEN
                CREATE SEQUENCE IF NOT EXISTS tenant_cohorts_id_seq;
                ALTER TABLE tenant_cohorts
                    ALTER COLUMN id SET DEFAULT nextval('tenant_cohorts_id_seq');
                ALTER SEQUENCE tenant_cohorts_id_seq
                    OWNED BY tenant_cohorts.id;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Leave sequences intact; removing defaults could break existing data.
    pass
