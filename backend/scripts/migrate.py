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


def get_sync_url(async_url: str) -> str:
    """Convert asyncpg URL to standard psycopg2 URL."""
    return async_url.replace("postgresql+asyncpg://", "postgresql://")


def check_migration_state():
    """Check current database state and determine action needed."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        return False

    sync_url = get_sync_url(db_url)
    
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            # Check if alembic_version table exists
            if "alembic_version" not in table_names:
                # No migration table
                if table_names:
                    # Schema exists but no migration tracking - this means tables were created
                    # by old migrations. Stamp with baseline to avoid re-creating.
                    print("✓ Detected existing schema without alembic_version table")
                    print("  Stamping database with baseline migration...")
                    result = subprocess.run(
                        ["alembic", "stamp", "317988fe2f1f"],
                        cwd=Path(__file__).parent.parent,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        print(f"ERROR: Failed to stamp migration: {result.stderr}")
                        return False
                    print("✓ Database stamped with baseline")
                    return True
                else:
                    # Fresh database, proceed with upgrade
                    print("✓ Fresh database detected, applying baseline migration...")
                    return True
            
            # Alembic table exists, check version
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result.fetchall()]
            
            if "317988fe2f1f" in versions and len(versions) == 1:
                # Already at baseline only
                print("✓ Database already at baseline migration")
                return True
            elif versions and "317988fe2f1f" not in versions:
                # Old migrations present, need to clear and stamp
                print(f"⚠ Detected old migration history: {versions}")
                print("  Clearing old entries and stamping with baseline...")
                conn.execute(text("DELETE FROM alembic_version"))
                conn.commit()
                
                result = subprocess.run(
                    ["alembic", "stamp", "317988fe2f1f"],
                    cwd=Path(__file__).parent.parent,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"ERROR: Failed to stamp migration: {result.stderr}")
                    return False
                print("✓ Database stamped with baseline")
                return True
            
            return True
            
    except Exception as e:
        print(f"⚠ Migration check warning (non-fatal): {e}")
        # Continue anyway - let alembic handle it
        return True
    finally:
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
