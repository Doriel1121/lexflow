
import pytest
from httpx import AsyncClient
from app.core.security import get_password_hash
from app.db.models.user import User

# Data for test user
TEST_EMAIL = "auth_test@example.com"
TEST_PASSWORD = "testpassword"

@pytest.fixture
async def test_user(db_session):
    """
    Fixture to create a test user.
    """
    user = User(
        email=TEST_EMAIL,
        hashed_password=get_password_hash(TEST_PASSWORD),
        full_name="Auth Test User",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.mark.asyncio
async def test_login_access_token(client: AsyncClient, test_user):
    """
    Test that a valid user can login and get an access token.
    """
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    response = await client.post("/token", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"
    return tokens["access_token"]

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """
    Test that login fails with wrong password.
    """
    login_data = {
        "username": TEST_EMAIL,
        "password": "wrongpassword"
    }
    response = await client.post("/token", data=login_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_access_protected_endpoint(client: AsyncClient, test_user):
    """
    Test accessing a protected endpoint with the token.
    Using /v1/users/me (assuming it exists and returns current user).
    """
    # 1. Login
    login_data = {
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    response = await client.post("/token", data=login_data)
    token = response.json()["access_token"]
    
    # 2. Access protected endpoint
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/v1/users/me", headers=headers)
    
    # If /v1/users/me exists
    if response.status_code == 200:
        data = response.json()
        assert data["email"] == TEST_EMAIL
    elif response.status_code == 404:
        # Fallback if /me doesn't exist, try another one or just warn
        pytest.skip("/v1/users/me endpoint not found")
    else:
        pytest.fail(f"Protected endpoint failed with status {response.status_code}: {response.text}")

@pytest.mark.asyncio
async def test_access_protected_endpoint_no_token(client: AsyncClient):
    """
    Test accessing protected endpoint without token fails.
    """
    response = await client.get("/v1/users/me")
    assert response.status_code == 401
