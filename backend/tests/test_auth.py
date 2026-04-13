import uuid

import pytest
from httpx import AsyncClient


def unique_email():
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": unique_email(),
        "password": "password123",
        "name": "New User",
        "company_name": "New Corp",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    email = unique_email()
    payload = {
        "email": email,
        "password": "password123",
        "name": "User",
        "company_name": "Corp",
    }
    resp1 = await client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201
    resp2 = await client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    email = unique_email()
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "User",
        "company_name": "Corp",
    })
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    email = unique_email()
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "User",
        "company_name": "Corp",
    })
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/api/auth/register", json={
        "email": unique_email(),
        "password": "password123",
        "name": "User",
        "company_name": "Corp",
    })
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    email = unique_email()
    reg = await client.post("/api/auth/register", json={
        "email": email,
        "password": "oldpass123",
        "name": "User",
        "company_name": "Corp",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/auth/change-password", json={
        "current_password": "oldpass123",
        "new_password": "newpass456",
    }, headers=headers)
    assert resp.status_code == 200

    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "newpass456",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_me(client: AsyncClient):
    email = unique_email()
    reg = await client.post("/api/auth/register", json={
        "email": email,
        "password": "password123",
        "name": "Me User",
        "company_name": "Me Corp",
    })
    token = reg.json()["access_token"]
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email
    assert data["name"] == "Me User"
    assert data["role"] == "owner"
