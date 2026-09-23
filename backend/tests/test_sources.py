import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.database import get_session_factory
from app.models.scraper import ScraperRegistry
from app.models.tenant import User
from app.services import scraper_analysis


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


# ── ② 접수·구독 (2026-09-23) ──

async def _register(client: AsyncClient) -> tuple[dict, str]:
    email = unique_email()
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": "password123", "name": "U", "company_name": "C",
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, email


@pytest.mark.asyncio
async def test_member_cannot_add_url(client: AsyncClient):
    headers, email = await _register(client)
    async with get_session_factory()() as db:
        await db.execute(update(User).where(User.email == email).values(role="member"))
        await db.commit()
    resp = await client.post("/api/sources", json={"url": f"https://m-{uuid.uuid4().hex[:6]}.com/b"},
                             headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_new_url_is_subscribed_immediately(client: AsyncClient):
    headers, _ = await _register(client)
    resp = await client.post("/api/sources", json={"url": f"https://n-{uuid.uuid4().hex[:6]}.com/b"},
                             headers=headers)
    data = resp.json()
    assert data["subscription_id"] is not None
    subs = (await client.get("/api/sources", headers=headers)).json()
    assert [(s["scraper_id"], s["scraper_status"]) for s in subs] == [(data["scraper_id"], "pending")]


@pytest.mark.asyncio
async def test_analysis_dispatched_once_per_new_url(client: AsyncClient):
    h1, _ = await _register(client)
    h2, _ = await _register(client)
    url = f"https://d-{uuid.uuid4().hex[:6]}.com/b"
    with patch("app.routers.sources._dispatch_analysis") as dispatch:
        r1 = await client.post("/api/sources", json={"url": url}, headers=h1)
        r2 = await client.post("/api/sources", json={"url": url}, headers=h1)  # 같은 회사 재제출
        r3 = await client.post("/api/sources", json={"url": url}, headers=h2)  # 다른 회사
    assert dispatch.call_count == 1
    assert r3.json()["scraper_id"] == r1.json()["scraper_id"]
    assert r3.json()["subscription_id"] not in (None, r1.json()["subscription_id"])
    assert r2.json()["subscription_id"] == r1.json()["subscription_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://127.0.0.1/admin", "http://169.254.169.254/latest", "file:///etc/passwd"])
async def test_unsafe_url_rejected_without_detail(client: AsyncClient, url):
    headers, _ = await _register(client)
    resp = await client.post("/api/sources", json={"url": url}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "사용할 수 없는 URL입니다"  # 원인은 로그에만


# ── 분석 실행과 상태 전이 (실제 DB, AI는 가짜) ──

async def _new_scraper_id(client: AsyncClient) -> int:
    headers, _ = await _register(client)
    resp = await client.post("/api/sources", json={"url": f"https://a-{uuid.uuid4().hex[:6]}.com/b"},
                             headers=headers)
    return resp.json()["scraper_id"]


async def _scraper(scraper_id: int) -> ScraperRegistry:
    async with get_session_factory()() as db:
        return (await db.execute(select(ScraperRegistry).where(ScraperRegistry.id == scraper_id))).scalar_one()


@pytest.mark.asyncio
async def test_run_analysis_marks_ready_with_config(client: AsyncClient, monkeypatch):
    scraper_id = await _new_scraper_id(client)

    async def fake_analyze(url):
        return {"name": "예시기관", "list_selector": "tr"}

    monkeypatch.setattr(scraper_analysis.scraper_ai, "analyze_url", fake_analyze)
    assert await scraper_analysis.run_analysis(scraper_id) == "ready"
    s = await _scraper(scraper_id)
    assert (s.status, s.name, s.scraper_config["list_selector"], s.analysis_log) == ("ready", "예시기관", "tr", None)


@pytest.mark.asyncio
async def test_run_analysis_marks_failed_with_reason(client: AsyncClient, monkeypatch):
    scraper_id = await _new_scraper_id(client)

    async def fake_analyze(url):
        raise ValueError("시험 수집 실패(3회 시도): 수집 0건")

    monkeypatch.setattr(scraper_analysis.scraper_ai, "analyze_url", fake_analyze)
    assert await scraper_analysis.run_analysis(scraper_id) == "failed"
    s = await _scraper(scraper_id)
    assert s.status == "failed" and "시험 수집 실패" in s.analysis_log


@pytest.mark.asyncio
async def test_run_analysis_unexpected_error_is_recorded_not_raised(client: AsyncClient, monkeypatch):
    scraper_id = await _new_scraper_id(client)

    async def boom(url):
        raise RuntimeError("예상 밖 오류")

    monkeypatch.setattr(scraper_analysis.scraper_ai, "analyze_url", boom)
    assert await scraper_analysis.run_analysis(scraper_id) == "failed"  # 백그라운드라 던지지 않는다
    assert (await _scraper(scraper_id)).status == "failed"
