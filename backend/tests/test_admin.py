import uuid

import pytest
from httpx import AsyncClient


def unique_email():
    return f"admin-{uuid.uuid4().hex[:8]}@example.com"


async def get_auth_headers(client: AsyncClient) -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": unique_email(),
        "password": "password123",
        "name": "Admin User",
        "company_name": "Admin Corp",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_collection_stats(client: AsyncClient):
    headers = await get_auth_headers(client)
    resp = await client.get("/api/admin/collection/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "bid_notices_count" in data
    assert "scraped_notices_count" in data
    assert "active_scrapers_count" in data
