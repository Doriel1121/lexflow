import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.db.models.user import User as DBUser
from app.schemas.user import UserCreate

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "email": "test@example.com",
        "password": "testpassword",
        "full_name": "Test User"
    }
    response = await client.post("/v1/users/", json=user_data)
    assert response.status_code == 201
    created_user = response.json()
    assert created_user["email"] == user_data["email"]
    assert created_user["full_name"] == user_data["full_name"]
    assert created_user["is_active"] is True
    assert created_user["is_superuser"] is False
    assert "id" in created_user

    # Verify user in database
    db_user = await db_session.get(DBUser, created_user["id"])
    assert db_user is not None
    assert db_user.email == user_data["email"]
    assert db_user.full_name == user_data["full_name"]
    assert db_user.is_active is True
    assert db_user.is_superuser is False
    assert get_password_hash(user_data["password"]) != user_data["password"] # Password should be hashed

@pytest.mark.asyncio
async def test_get_users(client: AsyncClient, db_session: AsyncSession):
    # Create a superuser and get token
    superuser_password = "supersecretpassword"
    superuser = DBUser(
        email="super@example.com",
        hashed_password=get_password_hash(superuser_password),
        full_name="Super User",
        is_superuser=True
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)

    token_response = await client.post(
        "/token",
        data={"username": superuser.email, "password": superuser_password}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    # Create a regular user
    regular_user_data = UserCreate(email="regular@example.com", password="regularpassword", full_name="Regular User")
    await client.post(
        "/v1/users/",
        json=regular_user_data.model_dump(),
        headers={"Authorization": f"Bearer {token}"}
    )

    response = await client.get("/v1/users/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 2 # Superuser and regular user
    assert any(u["email"] == "super@example.com" for u in users)
    assert any(u["email"] == "regular@example.com" for u in users)

@pytest.mark.asyncio
async def test_get_current_user_me(client: AsyncClient, db_session: AsyncSession):
    test_password = "testpassword"
    user = DBUser(email="test_me@example.com", hashed_password=get_password_hash(test_password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token_response = await client.post(
        "/token",
        data={"username": user.email, "password": test_password}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    response = await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    user_me = response.json()
    assert user_me["email"] == user.email

@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, db_session: AsyncSession):
    superuser_password = "supersecretpassword"
    superuser = DBUser(
        email="super_update@example.com",
        hashed_password=get_password_hash(superuser_password),
        full_name="Super Update User",
        is_superuser=True
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)

    token_response = await client.post(
        "/token",
        data={"username": superuser.email, "password": superuser_password}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    user_to_update = DBUser(email="old_email@example.com", hashed_password=get_password_hash("oldpassword"))
    db_session.add(user_to_update)
    await db_session.commit()
    await db_session.refresh(user_to_update)

    update_data = {"email": "new_email@example.com", "full_name": "New Full Name"}
    response = await client.put(
        f"/v1/users/{user_to_update.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["email"] == update_data["email"]
    assert updated_user["full_name"] == update_data["full_name"]

    db_user = await db_session.get(DBUser, user_to_update.id)
    assert db_user.email == update_data["email"]
    assert db_user.full_name == update_data["full_name"]

@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, db_session: AsyncSession):
    superuser_password = "supersecretpassword"
    superuser = DBUser(
        email="super_delete@example.com",
        hashed_password=get_password_hash(superuser_password),
        full_name="Super Delete User",
        is_superuser=True
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)

    token_response = await client.post(
        "/token",
        data={"username": superuser.email, "password": superuser_password}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    user_to_delete = DBUser(email="delete_me@example.com", hashed_password=get_password_hash("deleteme"))
    db_session.add(user_to_delete)
    await db_session.commit()
    await db_session.refresh(user_to_delete)

    response = await client.delete(
        f"/v1/users/{user_to_delete.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204

    db_user = await db_session.get(DBUser, user_to_delete.id)
    assert db_user is None
