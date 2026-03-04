"""
Integration tests for multi-tenant organization isolation (KAN-12, KAN-13)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User, UserRole
from app.db.models.organization import Organization
from app.db.models.case import Case, CaseStatus
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_independent_user_no_org_filter(client: AsyncClient, db_session: AsyncSession):
    """Test that independent users (org_id=NULL) can access their own data"""
    # Create independent user
    user = User(
        email="solo@lawyer.com",
        hashed_password="hashed",
        full_name="Solo Lawyer",
        organization_id=None,
        role=UserRole.LAWYER
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create JWT token
    token = create_access_token({
        "email": user.email,
        "user_id": user.id,
        "org_id": None,
        "role": "LAWYER"
    })
    
    # Test accessing cases
    response = await client.get(
        "/v1/cases/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_org_user_sees_only_org_data(client: AsyncClient, db_session: AsyncSession):
    """Test that organization users only see their org's data"""
    # Create two organizations
    org1 = Organization(name="Firm A", slug="firm-a")
    org2 = Organization(name="Firm B", slug="firm-b")
    db_session.add_all([org1, org2])
    await db_session.commit()
    
    # Create users in different orgs
    user1 = User(
        email="user1@firma.com",
        hashed_password="hashed",
        organization_id=org1.id,
        role=UserRole.LAWYER
    )
    user2 = User(
        email="user2@firmb.com",
        hashed_password="hashed",
        organization_id=org2.id,
        role=UserRole.LAWYER
    )
    db_session.add_all([user1, user2])
    await db_session.commit()
    
    # Create cases for each org
    case1 = Case(
        title="Case Org1",
        client_id=1,
        created_by_user_id=user1.id,
        organization_id=org1.id,
        status=CaseStatus.OPEN
    )
    case2 = Case(
        title="Case Org2",
        client_id=1,
        created_by_user_id=user2.id,
        organization_id=org2.id,
        status=CaseStatus.OPEN
    )
    db_session.add_all([case1, case2])
    await db_session.commit()
    
    # User1 token
    token1 = create_access_token({
        "email": user1.email,
        "user_id": user1.id,
        "org_id": org1.id,
        "role": "LAWYER"
    })
    
    # User1 should only see org1 cases
    response = await client.get(
        "/v1/cases/",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 1
    assert cases[0]["title"] == "Case Org1"


@pytest.mark.asyncio
async def test_cross_org_access_prevented(client: AsyncClient, db_session: AsyncSession):
    """Test that users cannot access data from other organizations"""
    org1 = Organization(name="Firm A", slug="firm-a")
    org2 = Organization(name="Firm B", slug="firm-b")
    db_session.add_all([org1, org2])
    await db_session.commit()
    
    user1 = User(
        email="user1@firma.com",
        hashed_password="hashed",
        organization_id=org1.id,
        role=UserRole.LAWYER
    )
    db_session.add(user1)
    await db_session.commit()
    
    case_org2 = Case(
        title="Case Org2",
        client_id=1,
        created_by_user_id=1,
        organization_id=org2.id,
        status=CaseStatus.OPEN
    )
    db_session.add(case_org2)
    await db_session.commit()
    
    token1 = create_access_token({
        "email": user1.email,
        "user_id": user1.id,
        "org_id": org1.id,
        "role": "LAWYER"
    })
    
    # Try to access case from org2
    response = await client.get(
        f"/v1/cases/{case_org2.id}",
        headers={"Authorization": f"Bearer {token1}"}
    )
    # Should return 404 (not found) because org filter prevents access
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_jwt_includes_org_id():
    """Test that JWT tokens include org_id"""
    token_data = {
        "email": "test@example.com",
        "user_id": 1,
        "org_id": 123,
        "role": "LAWYER"
    }
    token = create_access_token(token_data)
    
    from app.core.security import decode_access_token
    decoded = decode_access_token(token)
    
    assert decoded["email"] == "test@example.com"
    assert decoded["user_id"] == 1
    assert decoded["org_id"] == 123
    assert decoded["role"] == "LAWYER"
