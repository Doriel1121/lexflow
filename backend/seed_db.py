import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.base import Base
from app.core.config import settings
from app.db.models.user import User
from app.db.models.case import Case
from app.db.models.client import Client
from app.db.models.document import Document

async def seed_db():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Create dev user
        dev_user = User(
            email="dev@lexflow.com",
            hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIxHv8kLHy",  # password123
            full_name="Dev User",
            role="ADMIN",
            is_active=True
        )
        session.add(dev_user)
        await session.flush()
        
        # Create clients
        client1 = Client(
            name="Acme Corporation",
            contact_email="contact@acme.com",
            phone_number="+1-555-0100",
            address="123 Business St, New York, NY 10001"
        )
        client2 = Client(
            name="John Doe",
            contact_email="john.doe@email.com",
            phone_number="+1-555-0200",
            address="456 Residential Ave, Los Angeles, CA 90001"
        )
        session.add_all([client1, client2])
        await session.flush()
        
        # Create cases
        case1 = Case(
            title="Contract Dispute - Acme Corp",
            description="Commercial contract dispute regarding service delivery terms",
            status="OPEN",
            client_id=client1.id,
            created_by_user_id=dev_user.id
        )
        case2 = Case(
            title="Estate Planning - John Doe",
            description="Comprehensive estate planning and will preparation",
            status="OPEN",
            client_id=client2.id,
            created_by_user_id=dev_user.id
        )
        case3 = Case(
            title="Property Sale Agreement",
            description="Review and negotiation of commercial property sale",
            status="PENDING",
            client_id=client1.id,
            created_by_user_id=dev_user.id
        )
        session.add_all([case1, case2, case3])
        await session.flush()
        
        # Create documents
        doc1 = Document(
            filename="service_agreement.pdf",
            s3_url="/uploads/service_agreement.pdf",
            case_id=case1.id,
            uploaded_by_user_id=dev_user.id,
            content="Sample contract content...",
            classification="contract"
        )
        doc2 = Document(
            filename="will_draft_v1.docx",
            s3_url="/uploads/will_draft_v1.docx",
            case_id=case2.id,
            uploaded_by_user_id=dev_user.id,
            content="Sample will content...",
            classification="legal_document"
        )
        doc3 = Document(
            filename="property_deed.pdf",
            s3_url="/uploads/property_deed.pdf",
            case_id=case3.id,
            uploaded_by_user_id=dev_user.id,
            content="Sample property deed content...",
            classification="deed"
        )
        session.add_all([doc1, doc2, doc3])
        
        await session.commit()
    
    await engine.dispose()
    print("Database seeded with mock data!")

if __name__ == "__main__":
    asyncio.run(seed_db())
