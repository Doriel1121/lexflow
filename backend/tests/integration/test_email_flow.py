
import pytest
from httpx import AsyncClient
from app.core.security import get_password_hash
from app.db.models.user import User

# Reuse tests/conftest.py fixtures

@pytest.fixture
async def email_test_user(db_session):
    """
    Fixture to create a test user for email tests.
    """
    user = User(
        email="email_test@example.com",
        hashed_password=get_password_hash("testpassword"),
        full_name="Email Test User",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.mark.asyncio
async def test_get_email_accounts_unauth(client: AsyncClient):
    """
    Test that unauthenticated access fails.
    """
    response = await client.get("/v1/email/")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_email_flow(client: AsyncClient, email_test_user):
    """
    Test the full email flow: Login -> Get Accounts -> Sync -> Get Messages.
    """
    # 1. Login
    login_data = {
        "username": "email_test@example.com",
        "password": "testpassword"
    }
    response = await client.post("/token", data=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Accounts (Should auto-create one mock account)
    response = await client.get("/v1/email/", headers=headers)
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) >= 1
    account_id = accounts[0]["id"]
    assert accounts[0]["email_address"] == "email_test@example.com"

    # 3. Trigger Sync
    response = await client.post(f"/v1/email/{account_id}/sync", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "sync_started"

    # 4. Get Messages
    response = await client.get(f"/v1/email/{account_id}/messages", headers=headers)
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) >= 1
    assert messages[0]["subject"] == "New Legal Document #1"
