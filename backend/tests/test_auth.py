import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient, setup_roles):
    response = await client.post("/api/auth/register", json={
        "username": "testadmin",
        "email": "admin@test.com",
        "password": "Test123456",
        "full_name": "测试管理员",
        "role_id": 1,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testadmin"

    response = await client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "Test123456",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, setup_roles):
    await client.post("/api/auth/register", json={
        "username": "testuser2",
        "email": "user2@test.com",
        "password": "Correct123",
        "role_id": 2,
    })
    response = await client.post("/api/auth/login", json={
        "username": "testuser2",
        "password": "Wrong123",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_registration(client: AsyncClient, setup_roles):
    user_data = {
        "username": "dupuser",
        "email": "dup@test.com",
        "password": "Test123456",
        "role_id": 2,
    }
    await client.post("/api/auth/register", json=user_data)
    response = await client.post("/api/auth/register", json=user_data)
    assert response.status_code == 400
