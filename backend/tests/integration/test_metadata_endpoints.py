import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User as DBUser
from app.db.models.case import Case as DBCase
from app.db.models.client import Client as DBClient
from app.db.models.document import Document as DBDocument
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_extract_and_get_metadata_endpoint(client: AsyncClient, db_session: AsyncSession):
    """Test POST /documents/{id}/extract-metadata and GET /documents/{id}/metadata endpoints."""
    # Create test user
    user = DBUser(
        email="metadata@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Metadata User",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create test client
    test_client = DBClient(name="Metadata Client")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    # Create test case
    case = DBCase(
        title="Metadata Test Case",
        description="Test case",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    # Create document with content
    document = DBDocument(
        filename="contract.pdf",
        s3_url="http://storage.local/contract.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content="This Agreement dated 01/15/2024 between John Doe and Acme Corp Inc for $100,000. Case No. CV-2024-12345.",
        language="en",
        page_count=5
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # Login
    login_response = await client.post(
        "/token",
        data={"username": "metadata@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # Extract metadata
    extract_response = await client.post(
        f"/v1/documents/{document.id}/extract-metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert extract_response.status_code == 201
    metadata = extract_response.json()
    assert metadata["document_id"] == document.id
    assert len(metadata["dates"]) > 0
    assert len(metadata["amounts"]) > 0
    assert len(metadata["entities"]) > 0
    assert len(metadata["case_numbers"]) > 0
    
    # Get metadata
    get_response = await client.get(
        f"/v1/documents/{document.id}/metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert get_response.status_code == 200
    retrieved_metadata = get_response.json()
    assert retrieved_metadata["document_id"] == document.id
    assert retrieved_metadata["dates"] == metadata["dates"]


@pytest.mark.asyncio
async def test_extract_metadata_no_content(client: AsyncClient, db_session: AsyncSession):
    """Test metadata extraction fails when document has no content."""
    user = DBUser(
        email="nocontent@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="No Content User",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    test_client = DBClient(name="No Content Client")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    case = DBCase(
        title="No Content Case",
        description="Test",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    document = DBDocument(
        filename="empty.pdf",
        s3_url="http://storage.local/empty.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content=None
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    login_response = await client.post(
        "/token",
        data={"username": "nocontent@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    response = await client.post(
        f"/v1/documents/{document.id}/extract-metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "no content" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_metadata_not_found(client: AsyncClient, db_session: AsyncSession):
    """Test GET metadata returns 404 when metadata doesn't exist."""
    user = DBUser(
        email="nometa@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="No Meta User",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    test_client = DBClient(name="No Meta Client")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    case = DBCase(
        title="No Meta Case",
        description="Test",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    document = DBDocument(
        filename="test.pdf",
        s3_url="http://storage.local/test.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content="Some content"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    login_response = await client.post(
        "/token",
        data={"username": "nometa@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    response = await client.get(
        f"/v1/documents/{document.id}/metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert "metadata not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_extract_metadata_unauthorized(client: AsyncClient):
    """Test metadata extraction requires authentication."""
    response = await client.post("/v1/documents/1/extract-metadata")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_extract_metadata_updates_existing(client: AsyncClient, db_session: AsyncSession):
    """Test that re-extracting metadata updates existing record."""
    user = DBUser(
        email="update@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Update User",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    test_client = DBClient(name="Update Client")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    case = DBCase(
        title="Update Case",
        description="Test",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    document = DBDocument(
        filename="update.pdf",
        s3_url="http://storage.local/update.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content="Initial content with date 01/01/2024 and $1,000",
        language="en"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    login_response = await client.post(
        "/token",
        data={"username": "update@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # First extraction
    response1 = await client.post(
        f"/v1/documents/{document.id}/extract-metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response1.status_code == 201
    metadata1_id = response1.json()["id"]
    
    # Update document content
    document.content = "Updated content with date 12/31/2024 and $5,000"
    await db_session.commit()
    
    # Second extraction
    response2 = await client.post(
        f"/v1/documents/{document.id}/extract-metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 201
    metadata2 = response2.json()
    
    # Should update same record
    assert metadata2["id"] == metadata1_id
    assert "2024" in str(metadata2["dates"])


@pytest.mark.asyncio
async def test_viewer_cannot_extract_metadata(client: AsyncClient, db_session: AsyncSession):
    """Viewer users are not permitted to run metadata extraction."""
    viewer = DBUser(
        email="viewermeta@example.com",
        hashed_password=get_password_hash("pass"),
        full_name="Viewer Meta",
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()
    await db_session.refresh(viewer)

    document = DBDocument(
        filename="foo.pdf",
        s3_url="http://x",
        uploaded_by_user_id=viewer.id,
        content="some text"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    login = await client.post("/token", data={"username":"viewermeta@example.com","password":"pass"})
    token = login.json()["access_token"]

    res = await client.post(
        f"/v1/documents/{document.id}/extract-metadata",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403
