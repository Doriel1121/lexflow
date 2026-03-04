"""
Populate database with dummy data
Run: python seed_data.py
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.client import Client
from app.db.models.case import Case, CaseNote, CaseStatus
from app.db.models.document import Document
from app.db.models.tag import Tag
from app.db.models.summary import Summary
from app.core.security import get_password_hash

async def seed_data():
    async with AsyncSessionLocal() as db:
        # Create users
        user1 = User(
            email="admin@lexflow.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True
        )
        user2 = User(
            email="lawyer@lexflow.com",
            hashed_password=get_password_hash("lawyer123"),
            full_name="John Lawyer",
            is_active=True,
            is_superuser=False
        )
        db.add_all([user1, user2])
        await db.commit()
        await db.refresh(user1)
        await db.refresh(user2)
        print(f"✓ Created users: {user1.email}, {user2.email}")

        # Create clients
        clients = [
            Client(name="Acme Corporation", contact_person="Jane Smith", contact_email="jane@acme.com", phone_number="+1-555-0101", address="123 Business St, NY"),
            Client(name="Tech Innovations Inc", contact_person="Bob Johnson", contact_email="bob@techinno.com", phone_number="+1-555-0102", address="456 Tech Ave, CA"),
            Client(name="Global Solutions Ltd", contact_person="Alice Brown", contact_email="alice@global.com", phone_number="+1-555-0103", address="789 Global Rd, TX"),
        ]
        db.add_all(clients)
        await db.commit()
        for c in clients:
            await db.refresh(c)
        print(f"✓ Created {len(clients)} clients")

        # Create cases
        case1 = Case(title="Contract Dispute - Acme Corp", description="Dispute over service agreement terms", status="open", client_id=clients[0].id, created_by_user_id=user1.id)
        case2 = Case(title="Intellectual Property - Tech Innovations", description="Patent infringement case", status="pending", client_id=clients[1].id, created_by_user_id=user2.id)
        case3 = Case(title="Employment Agreement - Global Solutions", description="Review and negotiate employment contracts", status="open", client_id=clients[2].id, created_by_user_id=user1.id)
        case4 = Case(title="Merger & Acquisition - Acme Corp", description="Legal due diligence for acquisition", status="closed", client_id=clients[0].id, created_by_user_id=user2.id)
        cases = [case1, case2, case3, case4]
        db.add_all(cases)
        await db.commit()
        for c in cases:
            await db.refresh(c)
        print(f"✓ Created {len(cases)} cases")

        # Create case notes
        notes = [
            CaseNote(case_id=cases[0].id, user_id=user1.id, content="Initial consultation completed. Client wants to proceed with litigation."),
            CaseNote(case_id=cases[0].id, user_id=user2.id, content="Reviewed contract documents. Found several ambiguous clauses."),
            CaseNote(case_id=cases[1].id, user_id=user2.id, content="Patent search completed. Strong case for infringement."),
            CaseNote(case_id=cases[2].id, user_id=user1.id, content="Draft employment agreement sent to client for review."),
        ]
        db.add_all(notes)
        await db.commit()
        print(f"✓ Created {len(notes)} case notes")

        # Create tags
        tags = [
            Tag(name="contract"),
            Tag(name="litigation"),
            Tag(name="patent"),
            Tag(name="employment"),
            Tag(name="confidential"),
        ]
        db.add_all(tags)
        await db.commit()
        for t in tags:
            await db.refresh(t)
        print(f"✓ Created {len(tags)} tags")

        # Create documents
        documents = [
            Document(
                filename="service_agreement.pdf",
                s3_url="https://s3.example.com/docs/service_agreement.pdf",
                case_id=cases[0].id,
                uploaded_by_user_id=user1.id,
                content="This Service Agreement is entered into between Acme Corporation and Service Provider...",
                classification="contract",
                language="en"
            ),
            Document(
                filename="email_correspondence.pdf",
                s3_url="https://s3.example.com/docs/email_correspondence.pdf",
                case_id=cases[0].id,
                uploaded_by_user_id=user1.id,
                content="Email thread discussing contract terms and conditions...",
                classification="correspondence",
                language="en"
            ),
            Document(
                filename="patent_application.pdf",
                s3_url="https://s3.example.com/docs/patent_application.pdf",
                case_id=cases[1].id,
                uploaded_by_user_id=user2.id,
                content="Patent Application for innovative software algorithm...",
                classification="patent",
                language="en"
            ),
            Document(
                filename="employment_contract_draft.pdf",
                s3_url="https://s3.example.com/docs/employment_contract.pdf",
                case_id=cases[2].id,
                uploaded_by_user_id=user1.id,
                content="Employment Agreement between Global Solutions Ltd and Employee...",
                classification="contract",
                language="en"
            ),
        ]
        db.add_all(documents)
        await db.commit()
        for d in documents:
            await db.refresh(d)
        print(f"✓ Created {len(documents)} documents")

        # Add tags to documents
        documents[0].tags.append(tags[0])  # contract
        documents[0].tags.append(tags[1])  # litigation
        documents[1].tags.append(tags[4])  # confidential
        documents[2].tags.append(tags[2])  # patent
        documents[3].tags.append(tags[0])  # contract
        documents[3].tags.append(tags[3])  # employment
        await db.commit()
        print("✓ Added tags to documents")

        # Create summaries
        summaries = [
            Summary(
                document_id=documents[0].id,
                content="Service agreement between Acme Corp and provider. Key terms include payment schedule, deliverables, and termination clauses.",
                key_dates=["2024-01-15", "2024-06-30"],
                parties=["Acme Corporation", "Service Provider LLC"],
                missing_documents_suggestion="Need signed addendum and payment receipts"
            ),
            Summary(
                document_id=documents[2].id,
                content="Patent application for software algorithm. Claims innovative approach to data processing.",
                key_dates=["2024-03-01"],
                parties=["Tech Innovations Inc"],
                missing_documents_suggestion="Prior art search results needed"
            ),
        ]
        db.add_all(summaries)
        await db.commit()
        print(f"✓ Created {len(summaries)} summaries")

        print("\n✅ Database seeded successfully!")
        print("\nLogin credentials:")
        print("  Admin: admin@lexflow.com / admin123")
        print("  Lawyer: lawyer@lexflow.com / lawyer123")

if __name__ == "__main__":
    asyncio.run(seed_data())
