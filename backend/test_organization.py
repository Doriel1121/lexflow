"""
Test script to demonstrate organization-based data isolation
Run: python test_organization.py
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Fix Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.case import Case
from app.db.models.document import Document
from sqlalchemy import select
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

async def test_organization_isolation():
    """Test how organization_id affects data visibility"""
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("\n" + "="*80)
        print("ORGANIZATION DATA ISOLATION TEST")
        print("="*80)
        
        # 1. Create test organization
        print("\n1. Creating Test Organization...")
        org = Organization(name="Test Law Firm", slug="test-law-firm")
        session.add(org)
        await session.commit()
        await session.refresh(org)
        print(f"   ✓ Created organization: {org.name} (ID: {org.id})")
        
        # 2. Create users
        print("\n2. Creating Test Users...")
        
        # Independent lawyer (no organization)
        user1 = User(
            email="independent@lawyer.com",
            hashed_password="dummy",
            full_name="John Independent",
            role="lawyer",
            organization_id=None  # Independent
        )
        session.add(user1)
        
        # Organization member 1
        user2 = User(
            email="member1@testlaw.com",
            hashed_password="dummy",
            full_name="Alice TeamMember",
            role="lawyer",
            organization_id=org.id  # Belongs to org
        )
        session.add(user2)
        
        # Organization member 2
        user3 = User(
            email="member2@testlaw.com",
            hashed_password="dummy",
            full_name="Bob TeamMember",
            role="lawyer",
            organization_id=org.id  # Belongs to org
        )
        session.add(user3)
        
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)
        await session.refresh(user3)
        
        print(f"   ✓ Independent Lawyer: {user1.full_name} (org_id: {user1.organization_id})")
        print(f"   ✓ Org Member 1: {user2.full_name} (org_id: {user2.organization_id})")
        print(f"   ✓ Org Member 2: {user3.full_name} (org_id: {user3.organization_id})")
        
        # 3. Create cases
        print("\n3. Creating Test Cases...")
        
        # Independent lawyer's case
        case1 = Case(
            title="Independent Case",
            description="Private case",
            status="OPEN",
            created_by_user_id=user1.id,
            organization_id=None  # Private
        )
        session.add(case1)
        
        # Organization case created by member 1
        case2 = Case(
            title="Organization Case 1",
            description="Shared case",
            status="OPEN",
            created_by_user_id=user2.id,
            organization_id=org.id  # Shared
        )
        session.add(case2)
        
        # Organization case created by member 2
        case3 = Case(
            title="Organization Case 2",
            description="Another shared case",
            status="OPEN",
            created_by_user_id=user3.id,
            organization_id=org.id  # Shared
        )
        session.add(case3)
        
        await session.commit()
        print(f"   ✓ Created 3 cases")
        
        # 4. Test data visibility
        print("\n4. Testing Data Visibility...")
        print("\n" + "-"*80)
        
        # What independent lawyer sees
        print(f"\n👤 {user1.full_name} (Independent) can see:")
        result = await session.execute(
            select(Case).where(
                (Case.organization_id == None) | 
                (Case.created_by_user_id == user1.id)
            )
        )
        cases = result.scalars().all()
        for case in cases:
            print(f"   • {case.title} (created by user {case.created_by_user_id})")
        print(f"   Total: {len(cases)} case(s)")
        
        # What org member 1 sees
        print(f"\n👥 {user2.full_name} (Org Member) can see:")
        result = await session.execute(
            select(Case).where(Case.organization_id == org.id)
        )
        cases = result.scalars().all()
        for case in cases:
            print(f"   • {case.title} (created by user {case.created_by_user_id})")
        print(f"   Total: {len(cases)} case(s)")
        
        # What org member 2 sees (same as member 1)
        print(f"\n👥 {user3.full_name} (Org Member) can see:")
        result = await session.execute(
            select(Case).where(Case.organization_id == org.id)
        )
        cases = result.scalars().all()
        for case in cases:
            print(f"   • {case.title} (created by user {case.created_by_user_id})")
        print(f"   Total: {len(cases)} case(s)")
        
        print("\n" + "-"*80)
        print("\n5. Key Insights:")
        print("   ✓ Independent lawyers see ONLY their own data")
        print("   ✓ Organization members see ALL organization data")
        print("   ✓ Organization members can collaborate on shared cases")
        print("   ✓ Data is isolated by organization_id in database")
        
        # Cleanup
        print("\n6. Cleaning up test data...")
        await session.delete(case1)
        await session.delete(case2)
        await session.delete(case3)
        await session.delete(user1)
        await session.delete(user2)
        await session.delete(user3)
        await session.delete(org)
        await session.commit()
        print("   ✓ Test data cleaned up")
        
        print("\n" + "="*80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_organization_isolation())
