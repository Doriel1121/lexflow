"""
Idempotent seed script — safe to run on every deploy.
Skips creation if org/users already exist.
Credentials come from environment variables.
"""
import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.models.user import User, UserRole
from app.db.models.organization import Organization
from app.core.security import get_password_hash

SEED_ORG_NAME    = os.getenv("SEED_ORG_NAME", "LexFlow")
SEED_ORG_SLUG    = os.getenv("SEED_ORG_SLUG", "lexflow")
SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@lexflow.com")
SEED_ADMIN_PASS  = os.getenv("SEED_ADMIN_PASSWORD", "")
SEED_ORG_ADMIN_EMAIL = os.getenv("SEED_ORG_ADMIN_EMAIL", "orgadmin@lexflow.com")
SEED_ORG_ADMIN_PASS  = os.getenv("SEED_ORG_ADMIN_PASSWORD", "")


async def seed():
    if not SEED_ADMIN_PASS or not SEED_ORG_ADMIN_PASS:
        print("⚠ SEED_ADMIN_PASSWORD or SEED_ORG_ADMIN_PASSWORD not set — skipping seed.")
        return

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(User).where(User.email == SEED_ADMIN_EMAIL))
        if result.scalars().first():
            print("✓ Seed data already exists — skipping.")
            return

        # Create org
        result = await db.execute(select(Organization).where(Organization.slug == SEED_ORG_SLUG))
        org = result.scalars().first()
        if not org:
            org = Organization(name=SEED_ORG_NAME, slug=SEED_ORG_SLUG, is_active=True)
            db.add(org)
            await db.flush()
            print(f"✓ Created organization: {org.name}")

        # System admin (no org)
        db.add(User(
            email=SEED_ADMIN_EMAIL,
            full_name="System Admin",
            hashed_password=get_password_hash(SEED_ADMIN_PASS),
            role=UserRole.ADMIN,
            organization_id=None,
            is_active=True,
            is_superuser=True,
        ))

        # Org admin
        db.add(User(
            email=SEED_ORG_ADMIN_EMAIL,
            full_name="Org Admin",
            hashed_password=get_password_hash(SEED_ORG_ADMIN_PASS),
            role=UserRole.ORG_ADMIN,
            organization_id=org.id,
            is_active=True,
            is_superuser=False,
        ))

        await db.commit()
        print(f"✓ Seeded admin: {SEED_ADMIN_EMAIL}")
        print(f"✓ Seeded org admin: {SEED_ORG_ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(seed())
