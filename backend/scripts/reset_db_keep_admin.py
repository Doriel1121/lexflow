import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

async def wipe_db():
    async with AsyncSessionLocal() as db:
        print("Starting Database Wipe with Raw SQL...")
        
        # Check if super admin exists
        result = await db.execute(text("SELECT email FROM users WHERE email = 'doriel494@gmail.com'"))
        super_admin = result.fetchone()
        
        if not super_admin:
            print("WARNING: Super Admin doriel494@gmail.com not found! Skipping DB wipe.")
            return

        print(f"Preserving Super Admin: doriel494@gmail.com")
        
        # Unlink the super admin from any organization so we can delete the organizations
        await db.execute(text("UPDATE users SET organization_id = NULL WHERE email = 'doriel494@gmail.com'"))
        
        # Delete data in correct foreign-key order
        await db.execute(text("DELETE FROM audit_logs"))
        await db.execute(text("DELETE FROM case_notes"))
        await db.execute(text("DELETE FROM summaries"))
        await db.execute(text("DELETE FROM document_metadata"))
        await db.execute(text("DELETE FROM document_tag_association"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM cases"))
        await db.execute(text("DELETE FROM tags"))
        await db.execute(text("DELETE FROM email_messages"))
        await db.execute(text("DELETE FROM email_configs"))
        
        # Delete all users EXCEPT super admin
        await db.execute(text("DELETE FROM users WHERE email != 'doriel494@gmail.com'"))
        
        # Delete all Organizations
        await db.execute(text("DELETE FROM organizations"))
        
        await db.commit()
        print("Database wipe successfully completed using precise SQL bounds. Environment is fully sanitized for Multi-Tenant scaffolding.")

if __name__ == "__main__":
    asyncio.run(wipe_db())
