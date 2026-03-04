import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User as DBUser, UserRole
from app.db.models.case import Case as DBCase
from app.db.models.client import Client as DBClient
from app.db.models.document import Document as DBDocument
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_get_document_text_endpoint(client: AsyncClient, db_session: AsyncSession):
    """Test GET /documents/{id}/text endpoint returns OCR text with metadata."""
    # Create test user
    user = DBUser(
        email="test@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Test User",
        is_active=True,
        role=UserRole.LAWYER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create test client
    test_client = DBClient(name="Test Client")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    # Create test case
    case = DBCase(
        title="Test Case",
        description="Test case description",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    # Create test document with OCR data
    document = DBDocument(
        filename="test_document.pdf",
        s3_url="http://storage.local/test_document.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content="This is the full OCR extracted text from the document.",
        language="en",
        page_count=10,
        classification="contract"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # Login to get token
    login_response = await client.post(
        "/token",
        data={"username": "test@example.com", "password": "testpass"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Test GET /documents/{id}/text
    response = await client.get(
        f"/v1/documents/{document.id}/text",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == document.id
    assert data["filename"] == "test_document.pdf"
    assert data["content"] == "This is the full OCR extracted text from the document."
    assert data["language"] == "en"
    assert data["page_count"] == 10


@pytest.mark.asyncio
async def test_get_document_text_not_found(client: AsyncClient, db_session: AsyncSession):
    """Test GET /documents/{id}/text returns 404 for non-existent document."""
    # Create test user
    user = DBUser(
        email="test2@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Test User 2",
        is_active=True,
        role=UserRole.LAWYER,
    )
    db_session.add(user)
    await db_session.commit()
    
    # Login
    login_response = await client.post(
        "/token",
        data={"username": "test2@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # Test with non-existent document ID
    response = await client.get(
        "/v1/documents/99999/text",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_document_text_no_content(client: AsyncClient, db_session: AsyncSession):
    """Test GET /documents/{id}/text returns 404 when document has no OCR content."""
    # Create test user
    user = DBUser(
        email="test3@example.com",
        hashed_password=get_password_hash("testpass"),
        full_name="Test User 3",
        is_active=True,
        role=UserRole.LAWYER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create test client
    test_client = DBClient(name="Test Client 3")
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)
    
    # Create test case
    case = DBCase(
        title="Test Case 3",
        description="Test case",
        status="OPEN",
        client_id=test_client.id,
        created_by_user_id=user.id
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)
    
    # Create document without content
    document = DBDocument(
        filename="empty_doc.pdf",
        s3_url="http://storage.local/empty_doc.pdf",
        case_id=case.id,
        uploaded_by_user_id=user.id,
        content=None,
        language=None,
        page_count=None
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # Login
    login_response = await client.post(
        "/token",
        data={"username": "test3@example.com", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # Test endpoint
    response = await client.get(
        f"/v1/documents/{document.id}/text",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert "no ocr text" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_document_text_unauthorized(client: AsyncClient):
    """Test GET /documents/{id}/text requires authentication."""
    response = await client.get("/v1/documents/1/text")
    assert response.status_code == 401


# RBAC-specific scenarios
@pytest.mark.asyncio
async def test_viewer_cannot_add_tag(client: AsyncClient, db_session: AsyncSession):
    """Viewer users should receive 403 when trying to modify a document."""
    # create viewer user
    viewer = DBUser(
        email="viewer@example.com",
        hashed_password=get_password_hash("blah"),
        full_name="Viewer",
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()
    await db_session.refresh(viewer)

    # create a document belonging to the viewer
    doc = DBDocument(
        filename="foo.pdf",
        s3_url="http://x",
        uploaded_by_user_id=viewer.id,
        content="x"
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # login viewer
    login = await client.post("/token", data={"username":"viewer@example.com","password":"blah"})
    token = login.json()["access_token"]

    res = await client.post(
        f"/v1/documents/{doc.id}/tags",
        params={"tag_name":"test"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403

