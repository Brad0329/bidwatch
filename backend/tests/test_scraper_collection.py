"""URL 출처 수집 → scraped_notices 저장 (실제 DB, 수집기·DNS는 가짜)."""

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bid_collectors import Notice
from httpx import AsyncClient
from sqlalchemy import func, select

from app.database import get_session_factory
from app.models.scraper import ScrapedNotice, ScraperRegistry
from app.services import scraper_analysis, scraper_collection
from app.services.url_guard import UnsafeUrlError, guard_request

CONFIG = {
    "name": "예시기관", "source_key": "example", "list_url": "https://example.go.kr/board",
    "list_selector": "tr", "title_selector": "td a", "date_selector": "td.d",
}


def _notice(i: int) -> Notice:
    return Notice(source="예시기관", bid_no=f"SCR-example-{i}", title=f"시설물 유지보수 용역 입찰 공고 {i}",
                  organization="예시기관", url=f"https://example.go.kr/v/{i}", start_date=date.today())


@pytest.fixture
def fake_scraper(monkeypatch):
    state = {"notices": [_notice(1), _notice(2)], "errors": [], "raise": None, "calls": 0, "blocked": set(),
             "hooks": None}

    class FakeScraper:
        def __init__(self, config, event_hooks=None):
            self.config = config
            state["hooks"] = event_hooks

        async def collect(self, days=30):
            state["calls"] += 1
            if state["raise"]:
                raise state["raise"]
            return SimpleNamespace(notices=state["notices"], errors=state["errors"],
                                   is_partial=bool(state["errors"]))

    async def fake_guard(url):
        if any(b in url for b in state["blocked"]):
            raise UnsafeUrlError("공인 IP가 아님")

    async def fake_analyze(url):
        return dict(CONFIG)

    monkeypatch.setattr(scraper_collection, "GenericScraper", FakeScraper)
    monkeypatch.setattr(scraper_collection, "assert_safe_url", fake_guard)
    monkeypatch.setattr(scraper_analysis.scraper_ai, "analyze_url", fake_analyze)
    return state


async def _new_scraper(client: AsyncClient) -> int:
    resp = await client.post("/api/auth/register", json={
        "email": f"col-{uuid.uuid4().hex[:8]}@example.com", "password": "password123",
        "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = await client.post("/api/sources", json={"url": f"https://c-{uuid.uuid4().hex[:6]}.com/b"},
                             headers=headers)
    return resp.json()["scraper_id"]


async def _saved_count(scraper_id: int) -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(func.count()).select_from(ScrapedNotice)
                               .where(ScrapedNotice.scraper_id == scraper_id))


async def _row(scraper_id: int) -> ScraperRegistry:
    async with get_session_factory()() as db:
        return await db.get(ScraperRegistry, scraper_id)


@pytest.mark.asyncio
async def test_ready_analysis_collects_and_saves_immediately(client: AsyncClient, fake_scraper):
    scraper_id = await _new_scraper(client)
    assert await scraper_analysis.run_analysis(scraper_id) == "ready"
    assert await _saved_count(scraper_id) == 2
    row = await _row(scraper_id)
    assert row.last_collected_count == 2
    # 이 컬럼은 timestamptz(001 마이그레이션 timezone=True) — naive UTC로 써도 UTC 시각으로 저장돼야 한다
    age = datetime.now(timezone.utc) - row.last_collected_at
    assert abs(age.total_seconds()) < 120


@pytest.mark.asyncio
async def test_recollect_upserts_without_duplicates(client: AsyncClient, fake_scraper):
    scraper_id = await _new_scraper(client)
    await scraper_analysis.run_analysis(scraper_id)
    fake_scraper["notices"] = [_notice(1), _notice(2), _notice(3)]  # 기존 2건 + 새 1건
    result = await scraper_collection.collect_scraper(scraper_id)
    assert result["status"] == "ok"
    assert await _saved_count(scraper_id) == 3
    # 갱신된 행의 updated_at이 실제 현재 시각(UTC)이어야 한다 — utcnow()는 9시간 이르게 저장됐다
    async with get_session_factory()() as db:
        updated = await db.scalar(select(ScrapedNotice.updated_at).where(
            ScrapedNotice.scraper_id == scraper_id, ScrapedNotice.bid_no == "SCR-example-1"))
    assert abs((datetime.now(timezone.utc) - updated).total_seconds()) < 120


@pytest.mark.asyncio
async def test_system_source_stats_time_is_correct(client: AsyncClient):
    from app.models.notice import SystemSource
    from app.services.collection import update_source_stats

    async with get_session_factory()() as db:
        source_id = await db.scalar(select(SystemSource.id).limit(1))
        await update_source_stats(source_id, 7, db)
    async with get_session_factory()() as db:
        source = await db.get(SystemSource, source_id)
    assert source.last_collected_count == 7
    assert abs((datetime.now(timezone.utc) - source.last_collected_at).total_seconds()) < 120


@pytest.mark.asyncio
async def test_collect_failure_keeps_ready_and_is_reported(client: AsyncClient, fake_scraper):
    scraper_id = await _new_scraper(client)
    fake_scraper["raise"] = RuntimeError("사이트 응답 없음")
    assert await scraper_analysis.run_analysis(scraper_id) == "ready"  # 분석 결과는 유지
    row = await _row(scraper_id)
    assert row.status == "ready" and row.last_collected_count is None
    assert (await scraper_collection.collect_scraper(scraper_id))["status"] == "error"


@pytest.mark.asyncio
async def test_unsafe_config_url_is_not_requested(client: AsyncClient, fake_scraper):
    scraper_id = await _new_scraper(client)
    await scraper_analysis.run_analysis(scraper_id)  # 첫 수집은 정상
    assert fake_scraper["calls"] == 1
    fake_scraper["blocked"].add("example.go.kr")  # 그 뒤 DNS가 내부망으로 바뀐 경우
    result = await scraper_collection.collect_scraper(scraper_id)
    assert result["status"] == "error"
    assert fake_scraper["calls"] == 1  # 수집 요청이 나가지 않았다


@pytest.mark.asyncio
async def test_collect_requests_go_through_ssrf_hook(client: AsyncClient, fake_scraper):
    # 리다이렉트로 내부망에 가는 요청은 bid-collectors 훅으로만 막힌다 — 훅을 넘기는지
    scraper_id = await _new_scraper(client)
    await scraper_analysis.run_analysis(scraper_id)
    assert fake_scraper["hooks"] == {"request": [guard_request]}


@pytest.mark.asyncio
async def test_request_failure_is_error_not_zero_notices(client: AsyncClient, fake_scraper):
    # v1.1: 1페이지 실패는 0건 + errors — "공고 없음"으로 기록하면 사이트 장애가 가려진다
    scraper_id = await _new_scraper(client)
    await scraper_analysis.run_analysis(scraper_id)  # 첫 수집 2건
    fake_scraper["notices"], fake_scraper["errors"] = [], ["페이지 1 요청 실패: 차단"]
    result = await scraper_collection.collect_scraper(scraper_id)
    assert result["status"] == "error"
    assert (await _row(scraper_id)).last_collected_count == 2  # 0으로 덮지 않았다


@pytest.mark.asyncio
async def test_partial_collect_saves_and_reports(client: AsyncClient, fake_scraper):
    # max_pages 절단·N페이지 실패 — 받은 만큼 저장하고 partial을 알린다
    scraper_id = await _new_scraper(client)
    fake_scraper["errors"] = ["max_pages=3 상한 도달로 중단"]
    await scraper_analysis.run_analysis(scraper_id)
    result = await scraper_collection.collect_scraper(scraper_id)
    assert result["status"] == "ok" and result["partial"] is True
    assert await _saved_count(scraper_id) == 2


@pytest.mark.asyncio
async def test_preview_uses_ssrf_hook_and_hides_error_detail(client: AsyncClient, fake_scraper, monkeypatch):
    import bid_collectors

    monkeypatch.setattr(bid_collectors, "GenericScraper", scraper_collection.GenericScraper)  # 같은 가짜
    resp = await client.post("/api/auth/register", json={
        "email": f"pv-{uuid.uuid4().hex[:8]}@example.com", "password": "password123",
        "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    added = (await client.post("/api/sources", json={"url": f"https://p-{uuid.uuid4().hex[:6]}.com/b"},
                               headers=headers)).json()
    await scraper_analysis.run_analysis(added["scraper_id"])
    url = f"/api/sources/{added['subscription_id']}/preview"

    fake_scraper["hooks"] = None
    resp = await client.get(url, headers=headers)
    assert resp.status_code == 200 and resp.json()["notices_count"] == 2
    assert fake_scraper["hooks"] == {"request": [guard_request]}

    # 1페이지 실패는 "0건"이 아니라 오류로
    fake_scraper["notices"], fake_scraper["errors"] = [], ["페이지 1 요청 실패: http://10.0.0.1/"]
    resp = await client.get(url, headers=headers)
    assert resp.status_code == 502

    # 예외 원문(내부 주소 등)은 응답에 싣지 않는다
    fake_scraper["raise"] = RuntimeError("connect to 10.0.0.1 failed")
    resp = await client.get(url, headers=headers)
    assert resp.status_code == 500 and "10.0.0.1" not in resp.text


@pytest.mark.asyncio
async def test_titles_are_saved_with_normal_spaces(client: AsyncClient, fake_scraper):
    # 실측: 게시판 제목의 \xa0 때문에 키워드 '운영 대행'이 매칭되지 않았다
    fake_scraper["notices"] = [_notice(1).model_copy(update={"title": "크루즈\xa0포럼\xa0운영\xa0대행용역  입찰"})]
    scraper_id = await _new_scraper(client)
    await scraper_analysis.run_analysis(scraper_id)
    async with get_session_factory()() as db:
        title = await db.scalar(select(ScrapedNotice.title).where(ScrapedNotice.scraper_id == scraper_id))
    assert title == "크루즈 포럼 운영 대행용역 입찰"


@pytest.mark.asyncio
async def test_not_ready_scraper_is_skipped(client: AsyncClient, fake_scraper):
    scraper_id = await _new_scraper(client)  # 분석 전(pending)
    assert (await scraper_collection.collect_scraper(scraper_id))["status"] == "skipped"
    assert fake_scraper["calls"] == 0
