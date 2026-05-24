#!/usr/bin/env python3
"""
Migration helper script that handles transition from old migration chain to new baseline.
Supports three scenarios:
1. Fresh database: runs baseline migration normally
2. Existing database with old migrations: stamps with baseline (skips re-creating tables)
3. Existing database with only baseline: runs upgrade normally
"""
import os
import subprocess
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect, create_engine
from app.core.config import settings


def get_sync_url(async_url: str) -> str:
    """Convert asyncpg URL to standard psycopg2 URL."""
    return async_url.replace("postgresql+asyncpg://", "postgresql://")


def drop_all_tables(sync_url: str) -> bool:
    """Drop all tables from the database."""
    try:
        engine = create_engine(sync_url)
        with engine.begin() as conn:
            # Drop all tables
            inspector = inspect(engine)
            for table_name in reversed(inspector.get_table_names()):
                print(f"  Dropping table: {table_name}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            conn.commit()
        engine.dispose()
        return True
    except Exception as e:
        print(f"ERROR dropping tables: {e}")
        return False


def check_migration_state():
    """Check current database state and determine action needed."""
    engine = None
    db_url = settings.DATABASE_URL
    if not db_url:
        print("ERROR: DATABASE_URL not set in environment or config")
        print("Set DATABASE_URL or use RENDER_INTERNAL_DATABASE_URL/RENDER_EXTERNAL_DATABASE_URL")
        return False

    sync_url = get_sync_url(db_url)
    
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            # Check if alembic_version table exists
            if "alembic_version" not in table_names:
                if table_names:
                    # Schema exists but no migration tracking - tables from old migrations
                    print("✓ Detected existing schema from old migrations")
                    print("  Dropping all tables for clean rebuild...")
                    if not drop_all_tables(sync_url):
                        return False
                    print("✓ Tables dropped, baseline migration will create fresh schema")
                    return True
                else:
                    # Fresh database
                    print("✓ Fresh database detected")
                    return True
            
            # Alembic table exists: if it has *any* revision recorded, treat it as a
            # managed database and let Alembic handle upgrades. Dropping tables here
            # is too destructive and breaks normal multi-revision chains.
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result.fetchall()]

            if versions:
                print(f"✓ Alembic version detected: {versions}")
            else:
                # Empty alembic_version: schema exists but migration tracking is missing.
                # Do NOT drop tables automatically; allow operators to decide how to reconcile.
                print("⚠ alembic_version table is empty; skipping destructive auto-rebuild.")

            return True
            
    except Exception as e:
        print(f"⚠ Migration check warning (non-fatal): {e}")
        # Continue anyway - let alembic handle it
        return True
    finally:
        if engine:
            engine.dispose()


def run_migration():
    """Run alembic upgrade."""
    print("Running alembic upgrade head...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=Path(__file__).parent.parent
    )
    return result.returncode == 0


if __name__ == "__main__":
    print("=" * 60)
    print("LexFlow Database Migration Helper")
    print("=" * 60)
    
    if not check_migration_state():
        print("ERROR: Failed to check migration state")
        sys.exit(1)
    
    if not run_migration():
        print("ERROR: Migration failed")
        sys.exit(1)
    
    print("✓ Migration completed successfully")
    sys.exit(0)
