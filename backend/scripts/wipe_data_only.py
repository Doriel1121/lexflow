import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def wipe_data():
    async with AsyncSessionLocal() as db:
        print("Starting data-only wipe (preserving users and organizations)...")
        
        # 1. Clear document-related tables
        print("- Clearing document data...")
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(text("DELETE FROM summaries"))
        await db.execute(text("DELETE FROM document_metadata"))
        await db.execute(text("DELETE FROM document_tag_association"))
        await db.execute(text("DELETE FROM documents"))
        
        # 2. Clear case/collection-related tables
        print("- Clearing cases and tags...")
        await db.execute(text("DELETE FROM case_notes"))
        await db.execute(text("DELETE FROM deadlines"))
        await db.execute(text("DELETE FROM cases"))
        await db.execute(text("DELETE FROM tags"))
        
        # 3. Clear other transient data
        print("- Clearing logs and notifications...")
        await db.execute(text("DELETE FROM audit_logs"))
        await db.execute(text("DELETE FROM notifications"))
        await db.execute(text("DELETE FROM email_messages"))
        
        await db.commit()
        print("\nSUCCESS: All documents, cases, and collections have been deleted.")
        print("Users and Organizations were preserved.")

if __name__ == "__main__":
    asyncio.run(wipe_data())
