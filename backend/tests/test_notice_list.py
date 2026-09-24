"""공고 목록 — 공공 출처 + 직접 추가한 URL 출처를 한 목록으로 (실제 DB).

개발 DB에 실제 공고가 쌓여 있으므로, 테스트마다 고유 토큰을 키워드로 걸어 자기 데이터만 보이게 한다.
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select, update

from app.database import get_session_factory
from app.models.notice import BidNotice, SystemSource
from app.models.scraper import ScrapedNotice, ScraperRegistry


async def _tenant(client: AsyncClient, keyword: str | None = None) -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": f"nl-{uuid.uuid4().hex[:8]}@example.com", "password": "password123",
        "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    if keyword:
        r = await client.post("/api/keywords", json={"keyword": keyword}, headers=headers)
        assert r.status_code == 201, r.text
    return headers


async def _url_source_with_notices(client, headers, token: str, n: int, name: str = "예시기관") -> dict:
    """URL을 추가하고(분석은 conftest가 막음) ready로 만든 뒤 공고 n건을 넣는다."""
    resp = await client.post("/api/sources", json={"url": f"https://u-{uuid.uuid4().hex[:6]}.com/b"},
                             headers=headers)
    data = resp.json()
    async with get_session_factory()() as db:
        await db.execute(update(ScraperRegistry).where(ScraperRegistry.id == data["scraper_id"])
                         .values(status="ready", name=name))
        for i in range(n):
            db.add(ScrapedNotice(scraper_id=data["scraper_id"], bid_no=f"SCR-{token}-{i}",
                                 title=f"{token} 시설 유지보수 용역 {i}", organization=name,
                                 url=f"https://example.go.kr/{i}", start_date=date.today() - timedelta(days=i)))
        await db.commit()
    return data


@pytest_asyncio.fixture
async def bid_notice(client: AsyncClient):
    """공공 출처(첫 번째 system_source)에 공고 1건을 넣고 (source_id, notice_id)를 돌려주는 팩토리.

    bid_notices는 모든 테넌트가 공유하는 실제 공고 테이블이라, 넣은 행을 끝나면 지운다
    (지우지 않아 개발 DB에 'T-' 공고 28건이 쌓여 제목 빈도 분석을 오염시킨 실사례, 2026-09-24).
    client에 의존해 엔진이 dispose되기 전에 정리한다.
    """
    created: list[int] = []

    async def make(token: str) -> tuple[int, int]:
        async with get_session_factory()() as db:
            source_id = await db.scalar(select(SystemSource.id).order_by(SystemSource.id).limit(1))
            notice = BidNotice(source_id=source_id, bid_no=f"T-{token}", title=f"{token} 청사 공사 입찰",
                               organization="어느기관", url="https://example.go.kr/bid",
                               start_date=date.today() + timedelta(days=1))
            db.add(notice)
            await db.commit()
            created.append(notice.id)
            return source_id, notice.id

    yield make

    if created:
        async with get_session_factory()() as db:
            await db.execute(delete(BidNotice).where(BidNotice.id.in_(created)))
            await db.commit()


async def _list(client, headers, **params) -> dict:
    resp = await client.get("/api/notices", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_subscribed_url_notices_appear_in_list(client: AsyncClient):
    token = uuid.uuid4().hex[:10]
    headers = await _tenant(client, keyword=token)
    src = await _url_source_with_notices(client, headers, token, 2, name="강원관광재단")
    data = await _list(client, headers)
    assert data["total"] == 2
    assert {(i["notice_type"], i["source_id"], i["source_name"]) for i in data["items"]} == \
        {("scraped", src["scraper_id"], "강원관광재단")}
    assert all(token in i["matched_keywords"] for i in data["items"])


@pytest.mark.asyncio
async def test_other_tenant_without_subscription_does_not_see_them(client: AsyncClient):
    token = uuid.uuid4().hex[:10]
    owner = await _tenant(client, keyword=token)
    await _url_source_with_notices(client, owner, token, 2)
    stranger = await _tenant(client, keyword=token)
    assert (await _list(client, stranger))["total"] == 0


@pytest.mark.asyncio
async def test_unsubscribed_url_notices_disappear(client: AsyncClient):
    token = uuid.uuid4().hex[:10]
    headers = await _tenant(client, keyword=token)
    src = await _url_source_with_notices(client, headers, token, 2)
    await client.delete(f"/api/sources/{src['subscription_id']}", headers=headers)
    assert (await _list(client, headers))["total"] == 0


@pytest.mark.asyncio
async def test_bid_and_url_notices_merge_with_total_and_pages(client: AsyncClient, bid_notice):
    token = uuid.uuid4().hex[:10]
    headers = await _tenant(client, keyword=token)
    source_id, bid_id = await bid_notice(token)
    await client.post(f"/api/sources/system/{source_id}/subscribe", headers=headers)
    await _url_source_with_notices(client, headers, token, 2)

    p1 = await _list(client, headers, page_size=2, page=1)
    p2 = await _list(client, headers, page_size=2, page=2)
    assert p1["total"] == p2["total"] == 3                      # 합친 뒤 기준 전체 건수
    keys = [(i["notice_type"], i["id"]) for i in p1["items"] + p2["items"]]
    assert len(keys) == len(set(keys)) == 3                      # 페이지 사이 중복·누락 없음
    assert keys[0] == ("bid", bid_id)                            # 등록일 최신(내일)이 맨 앞


@pytest.mark.asyncio
async def test_source_and_scraper_filters_narrow_to_one_kind(client: AsyncClient, bid_notice):
    token = uuid.uuid4().hex[:10]
    headers = await _tenant(client, keyword=token)
    source_id, _ = await bid_notice(token)
    await client.post(f"/api/sources/system/{source_id}/subscribe", headers=headers)
    src = await _url_source_with_notices(client, headers, token, 2)

    only_bid = await _list(client, headers, source_id=source_id)
    only_url = await _list(client, headers, scraper_id=src["scraper_id"])
    assert {i["notice_type"] for i in only_bid["items"]} == {"bid"} and only_bid["total"] == 1
    assert {i["notice_type"] for i in only_url["items"]} == {"scraped"} and only_url["total"] == 2


@pytest.mark.asyncio
async def test_tag_on_url_notice_filters_and_shows(client: AsyncClient):
    token = uuid.uuid4().hex[:10]
    headers = await _tenant(client, keyword=token)
    await _url_source_with_notices(client, headers, token, 2)
    target = (await _list(client, headers))["items"][0]
    r = await client.put("/api/tags", json={"notice_type": "scraped", "notice_id": target["id"], "tag": "검토요청"},
                         headers=headers)
    assert r.status_code in (200, 201), r.text

    tagged = await _list(client, headers, tag="검토요청")
    assert [(i["notice_type"], i["id"], i["tag"]) for i in tagged["items"]] == \
        [("scraped", target["id"], "검토요청")]


@pytest.mark.asyncio
async def test_scraped_detail_only_for_subscribers(client: AsyncClient):
    token = uuid.uuid4().hex[:10]
    owner = await _tenant(client, keyword=token)
    await _url_source_with_notices(client, owner, token, 1, name="강원관광재단")
    notice = (await _list(client, owner))["items"][0]

    ok = await client.get(f"/api/notices/scraped/{notice['id']}", headers=owner)
    assert ok.status_code == 200
    assert (ok.json()["notice_type"], ok.json()["source_name"]) == ("scraped", "강원관광재단")

    stranger = await _tenant(client)
    denied = await client.get(f"/api/notices/scraped/{notice['id']}", headers=stranger)
    assert denied.status_code == 404
