"""
Idempotent seed script using raw SQL — safe to run on every deploy.
Avoids ORM model imports which can fail if schema doesn't match model exactly.
"""
import asyncio
import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Load .env from repo root for local testing
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

DATABASE_URL      = os.environ["DATABASE_URL"]
SEED_ORG_NAME     = os.getenv("SEED_ORG_NAME", "LexFlow")
SEED_ORG_SLUG     = os.getenv("SEED_ORG_SLUG", "lexflow")
SEED_ADMIN_EMAIL  = os.getenv("SEED_ADMIN_EMAIL", "admin@lexflow.com")
SEED_ADMIN_PASS   = os.getenv("SEED_ADMIN_PASSWORD", "")
SEED_ORG_ADMIN_EMAIL = os.getenv("SEED_ORG_ADMIN_EMAIL", "orgadmin@lexflow.com")
SEED_ORG_ADMIN_PASS  = os.getenv("SEED_ORG_ADMIN_PASSWORD", "")

def hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except Exception:
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_ctx.hash(password)


async def seed():
    if not SEED_ADMIN_PASS or not SEED_ORG_ADMIN_PASS:
        print("⚠ Seed passwords not set — skipping seed.")
        return

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": SEED_ADMIN_EMAIL}
        )
        if result.fetchone():
            print("[SKIP] Seed data already exists — skipping.")
            await engine.dispose()
            return

        # Create org
        result = await db.execute(
            text("SELECT id FROM organizations WHERE slug = :slug"),
            {"slug": SEED_ORG_SLUG}
        )
        org_row = result.fetchone()
        if org_row:
            org_id = org_row[0]
        else:
            result = await db.execute(
                text("INSERT INTO organizations (name, slug, is_active) VALUES (:name, :slug, true) RETURNING id"),
                {"name": SEED_ORG_NAME, "slug": SEED_ORG_SLUG}
            )
            org_id = result.fetchone()[0]
            print(f"[OK] Created organization: {SEED_ORG_NAME}")

        # Check if role column exists
        role_check = await db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='users' AND column_name='role'
        """))
        has_role = role_check.fetchone() is not None

        # Check if organization_id column exists on users
        org_col_check = await db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='users' AND column_name='organization_id'
        """))
        has_org_col = org_col_check.fetchone() is not None

        # System admin
        if has_role:
            await db.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser, role)
                VALUES (:email, :pw, 'System Admin', true, true, 'admin')
            """), {"email": SEED_ADMIN_EMAIL, "pw": hash_password(SEED_ADMIN_PASS)})
        else:
            await db.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser)
                VALUES (:email, :pw, 'System Admin', true, true)
            """), {"email": SEED_ADMIN_EMAIL, "pw": hash_password(SEED_ADMIN_PASS)})

        # Org admin
        if has_role and has_org_col:
            await db.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser, role, organization_id)
                VALUES (:email, :pw, 'Org Admin', true, false, 'org_admin', :org_id)
            """), {"email": SEED_ORG_ADMIN_EMAIL, "pw": hash_password(SEED_ORG_ADMIN_PASS), "org_id": org_id})
        else:
            await db.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, is_active, is_superuser)
                VALUES (:email, :pw, 'Org Admin', true, false)
            """), {"email": SEED_ORG_ADMIN_EMAIL, "pw": hash_password(SEED_ORG_ADMIN_PASS)})

        await db.commit()
        print(f"[OK] Seeded admin: {SEED_ADMIN_EMAIL}")
        print(f"[OK] Seeded org admin: {SEED_ORG_ADMIN_EMAIL}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
