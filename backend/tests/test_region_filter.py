"""지역 필터 — 지역을 고르면 그 지역 공고 + 지역을 모르는 공고(빈 값)가 나온다 (F-011, 2026-09-24 변경).

알리오·나라장터 사전규격·직접 추가 사이트는 지역이 100% 빈 값이라, 빈 값을 빼면 통째로 가려진다.
공유 테이블(bid_notices)에 넣은 행은 끝나면 지운다 — 테스트가 개발 DB를 쓴다.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.database import get_session_factory
from app.models.notice import BidNotice, SystemSource


@pytest_asyncio.fixture
async def regional_notices(client: AsyncClient):
    """collector_type 출처에 서울·부산·빈 지역 공고 3건을 넣는 팩토리. 제목에 token을 넣어 키워드로 격리한다."""
    created: list[int] = []

    async def make(collector_type: str, token: str) -> int:
        async with get_session_factory()() as db:
            source_id = await db.scalar(select(SystemSource.id).where(SystemSource.collector_type == collector_type))
            for region in ("서울", "부산", ""):
                n = BidNotice(source_id=source_id, bid_no=f"RG-{token}-{region or 'none'}",
                              title=f"{token} 지역 {region or '미상'} 용역", organization="어느기관",
                              url="https://example.go.kr/r", region=region, start_date=date.today())
                db.add(n)
                await db.flush()
                created.append(n.id)
            await db.commit()
        return source_id

    yield make

    async with get_session_factory()() as db:
        await db.execute(delete(BidNotice).where(BidNotice.id.in_(created)))
        await db.commit()


async def _tenant_with_keyword(client: AsyncClient, keyword: str) -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": f"rg-{uuid.uuid4().hex[:8]}@example.com", "password": "password123",
        "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert (await client.post("/api/keywords", json={"keyword": keyword}, headers=headers)).status_code == 201
    return headers


def _regions(resp) -> list[str]:
    assert resp.status_code == 200, resp.text
    return sorted(item["region"] for item in resp.json()["items"])


@pytest.mark.asyncio
async def test_region_filter_keeps_unknown_region(client: AsyncClient, regional_notices):
    token = uuid.uuid4().hex[:10]
    source_id = await regional_notices("nara", token)
    headers = await _tenant_with_keyword(client, token)
    assert (await client.post(f"/api/sources/system/{source_id}/subscribe", headers=headers)).status_code == 200

    everything = await client.get("/api/notices", params={}, headers=headers)
    assert _regions(everything) == ["", "부산", "서울"]
    only_seoul = await client.get("/api/notices", params={"region": "서울"}, headers=headers)
    assert _regions(only_seoul) == ["", "서울"]  # 부산만 빠지고 지역 미상은 남는다
    assert only_seoul.json()["total"] == 2


@pytest.mark.asyncio
async def test_prespec_region_filter_keeps_unknown_region(client: AsyncClient, regional_notices):
    token = uuid.uuid4().hex[:10]
    await regional_notices("nara_prespec", token)
    headers = await _tenant_with_keyword(client, token)

    only_seoul = await client.get("/api/notices/pre-specs", params={"region": "서울"}, headers=headers)
    assert _regions(only_seoul) == ["", "서울"]
    assert only_seoul.json()["total"] == 2
