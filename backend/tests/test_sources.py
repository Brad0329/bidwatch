import uuid

import pytest
from httpx import AsyncClient


def unique_email():
    return f"src-{uuid.uuid4().hex[:8]}@example.com"


async def get_auth_headers(client: AsyncClient) -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": unique_email(),
        "password": "password123",
        "name": "Source User",
        "company_name": "Source Corp",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_system_sources(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.get("/api/sources/system", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_subscriptions_empty(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.get("/api/sources", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_source_creates_scraper(client: AsyncClient):
    """URL 제출 시 scraper_registry에 등록되고 pending 상태 반환."""
    headers = await get_auth_headers(client)
    test_url = f"https://example-{uuid.uuid4().hex[:6]}.com/board/list"
    resp = await client.post("/api/sources", json={"url": test_url}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scraper_id"] > 0
    assert data["scraper_status"] == "pending"


@pytest.mark.asyncio
async def test_add_same_url_twice(client: AsyncClient):
    """같은 URL을 두 번 제출하면 같은 scraper_id 반환."""
    headers = await get_auth_headers(client)
    test_url = f"https://same-{uuid.uuid4().hex[:6]}.com/board"
    resp1 = await client.post("/api/sources", json={"url": test_url}, headers=headers)
    resp2 = await client.post("/api/sources", json={"url": test_url}, headers=headers)
    assert resp1.json()["scraper_id"] == resp2.json()["scraper_id"]
