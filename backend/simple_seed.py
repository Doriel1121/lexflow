"""Simple seed script"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.client import Client
from app.db.models.case import Case, CaseNote, CaseStatus
from app.db.models.document import Document
from app.core.security import get_password_hash

async def seed():
    async with AsyncSessionLocal() as db:
        # Get existing users
        result = await db.execute(select(User))
        users = list(result.scalars().all())
        if not users:
            print("No users found!")
            return
        user = users[0]
        print(f"Using user: {user.email}")

        # Create clients if needed
        result = await db.execute(select(Client))
        clients = list(result.scalars().all())
        if not clients:
            c1 = Client(name="Acme Corp", contact_email="acme@test.com")
            c2 = Client(name="Tech Inc", contact_email="tech@test.com")
            db.add_all([c1, c2])
            await db.commit()
            await db.refresh(c1)
            await db.refresh(c2)
            clients = [c1, c2]
            print(f"Created {len(clients)} clients")
        else:
            print(f"Found {len(clients)} existing clients")

        # Create cases
        result = await db.execute(select(Case))
        existing_cases = list(result.scalars().all())
        if not existing_cases:
            case1 = Case(
                title="Contract Dispute",
                description="Service agreement dispute",
                status=CaseStatus.OPEN,
                client_id=clients[0].id,
                created_by_user_id=user.id
            )
            case2 = Case(
                title="Patent Case",
                description="IP infringement",
                status=CaseStatus.PENDING,
                client_id=clients[1].id,
                created_by_user_id=user.id
            )
            db.add_all([case1, case2])
            await db.commit()
            await db.refresh(case1)
            await db.refresh(case2)
            print(f"Created 2 cases")
            
            # Add notes
            note = CaseNote(case_id=case1.id, user_id=user.id, content="Initial consultation completed")
            db.add(note)
            await db.commit()
            print("Created case note")
            
            # Add documents
            doc1 = Document(
                filename="contract.pdf",
                s3_url="https://example.com/contract.pdf",
                case_id=case1.id,
                uploaded_by_user_id=user.id,
                content="Contract agreement text...",
                classification="contract",
                language="en"
            )
            doc2 = Document(
                filename="patent.pdf",
                s3_url="https://example.com/patent.pdf",
                case_id=case2.id,
                uploaded_by_user_id=user.id,
                content="Patent application text...",
                classification="patent",
                language="en"
            )
            db.add_all([doc1, doc2])
            await db.commit()
            print("Created 2 documents")
        else:
            print(f"Found {len(existing_cases)} existing cases")

        print("\n✅ Done! Refresh your browser.")

if __name__ == "__main__":
    asyncio.run(seed())
