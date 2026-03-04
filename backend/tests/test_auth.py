import pytest
from httpx import AsyncClient
from app.db.models.user import User as DBUser, UserRole
from app.core.security import get_password_hash, decode_access_token


@pytest.mark.asyncio
async def test_password_login_returns_token_with_role(client, db_session):
    # prepare a user with a known role
    user = DBUser(
        email="jane.doe@example.com",
        hashed_password=get_password_hash("secret"),
        full_name="Jane Doe",
        role=UserRole.LAWYER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    response = await client.post(
        "/token",
        data={"username": "jane.doe@example.com", "password": "secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    token = body["access_token"]

    payload = decode_access_token(token)
    assert payload is not None
    assert payload.get("email") == "jane.doe@example.com"
    assert payload.get("role") == user.role.value
    assert payload.get("user_id") == user.id


@pytest.mark.asyncio
async def test_dev_login_creates_admin_if_missing(client, db_session):
    # dev-login should create an admin user when email not found
    email = "dev@company.com"
    response = await client.get(f"/v1/auth/dev-login?email={email}")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == email
    assert data["user"]["role"] == UserRole.ADMIN.value
    assert "access_token" in data

    # subsequent calls should not create a second user
    response2 = await client.get(f"/v1/auth/dev-login?email={email}")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["user"]["id"] == data["user"]["id"]
