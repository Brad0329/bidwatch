"""알리오 상세 보강 (F-007, bid-collectors v1.3.0 AlioCollector.fetch_detail).

팝업을 열 때(상세 API) 한 번만 조회해 첨부·원문 링크를 저장하고, 원문 링크의 나라장터 공고번호로 나라장터 공고를 잇는다.
fetch_detail은 가짜로 바꾼다(알리오 실호출 없음). 공유 테이블에 넣은 행은 끝나면 지운다 — 테스트가 개발 DB를 쓴다.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from bid_collectors.models import Notice
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.database import get_session_factory
from app.models.notice import BidNotice, SystemSource
from app.services.collection import upsert_bid_notices


@pytest_asyncio.fixture
async def alio_setup(client: AsyncClient):
    """알리오 공고 2건(첨부 있음·없음) + 같은 나라장터 공고 2차수 + 키워드 걸린 테넌트."""
    t = uuid.uuid4().hex[:8]
    g2b_no = f"R26BK{t}"
    async with get_session_factory()() as db:
        ids = dict((await db.execute(select(SystemSource.collector_type, SystemSource.id))).all())
        await upsert_bid_notices([
            Notice(source="알리오", bid_no=f"ALIO-{t}1", title=f"{t} 알리오 공고", organization="어느공단",
                   url="https://alio.go.kr/x", extra={"seq": 1, "rtitle": f"{t} 알리오 공고"}),
            Notice(source="알리오", bid_no=f"ALIO-{t}2", title=f"{t} 첨부 없는 공고", organization="어느공단",
                   url="https://alio.go.kr/y", extra={"seq": 2}),
        ], ids["alio"], db)
        await upsert_bid_notices([
            Notice(source="나라장터", bid_no=f"용역-{g2b_no}-{o}", title=f"{t} 나라장터 {o}", organization="어느공단",
                   url="https://g2b.go.kr", extra={"bidNtceNo": g2b_no, "bidNtceOrd": o})
            for o in ("000", "001")
        ], ids["nara"], db)
        rows = {n.bid_no: n.id for n in (await db.execute(
            select(BidNotice).where(BidNotice.bid_no.contains(t)))).scalars()}

    resp = await client.post("/api/auth/register", json={
        "email": f"al-{uuid.uuid4().hex[:8]}@example.com", "password": "password123", "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    yield t, g2b_no, rows, headers

    async with get_session_factory()() as db:
        await db.execute(delete(BidNotice).where(BidNotice.bid_no.contains(t)))
        await db.commit()


def _detail(g2b_no: str, files: int) -> dict:
    return {
        "attachments": [{"name": f"공고문{i}.hwp", "url": f"https://www.g2b.go.kr/f{i}"} for i in range(files)],
        "content": "",
        "refrUrl": f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={g2b_no}&bidPbancOrd=001",
        "bidType": "1", "totContAmt": 0, "seq": "999",
    }


@pytest.mark.asyncio
async def test_alio_detail_fetched_once_and_stored(client: AsyncClient, alio_setup):
    t, g2b_no, rows, headers = alio_setup
    fake = AsyncMock(return_value=_detail(g2b_no, 2))
    with patch("app.services.notice._fetch_detail_via_collector", fake):
        first = (await client.get(f"/api/notices/{rows[f'ALIO-{t}1']}", headers=headers)).json()
        second = (await client.get(f"/api/notices/{rows[f'ALIO-{t}1']}", headers=headers)).json()

    assert fake.await_count == 1  # 두 번째 열기는 조회하지 않는다
    assert [a["name"] for a in first["attachments"]] == ["공고문0.hwp", "공고문1.hwp"]
    assert second["attachments"] == first["attachments"]
    assert first["extra"]["refrUrl"].startswith("https://www.g2b.go.kr/")
    assert first["extra"]["totContAmt"] == 0  # 0도 원문 값이다
    assert first["extra"]["seq"] == 1  # 목록에서 온 값은 덮지 않는다


@pytest.mark.asyncio
async def test_alio_without_attachments_is_not_refetched(client: AsyncClient, alio_setup):
    t, g2b_no, rows, headers = alio_setup
    fake = AsyncMock(return_value=_detail(g2b_no, 0))
    with patch("app.services.notice._fetch_detail_via_collector", fake):
        first = (await client.get(f"/api/notices/{rows[f'ALIO-{t}2']}", headers=headers)).json()
        await client.get(f"/api/notices/{rows[f'ALIO-{t}2']}", headers=headers)

    assert first["attachments"] == []
    assert fake.await_count == 1


@pytest.mark.asyncio
async def test_alio_links_to_latest_nara_notice(client: AsyncClient, alio_setup):
    t, g2b_no, rows, headers = alio_setup
    with patch("app.services.notice._fetch_detail_via_collector", AsyncMock(return_value=_detail(g2b_no, 1))):
        linked = (await client.get(f"/api/notices/{rows[f'ALIO-{t}1']}", headers=headers)).json()
    assert [(r["kind"], r["bid_no"]) for r in linked["related"]] == [("nara", f"용역-{g2b_no}-001")]

    # 원문 링크가 나라장터가 아니면(온비드 등) 연결 없음
    onbid = {**_detail(g2b_no, 1), "refrUrl": "https://www.onbid.co.kr/op/cta/cltrdtl/x.do?cltrNo=1"}
    with patch("app.services.notice._fetch_detail_via_collector", AsyncMock(return_value=onbid)):
        other = (await client.get(f"/api/notices/{rows[f'ALIO-{t}2']}", headers=headers)).json()
    assert other["related"] == []


@pytest.mark.asyncio
async def test_alio_detail_failure_keeps_popup(client: AsyncClient, alio_setup):
    """fetch_detail 실패(없는 seq·장애 — v1.3.0은 예외)는 경고 로그만, 팝업 응답은 200이고 다음에 다시 시도한다."""
    t, _, rows, headers = alio_setup
    with patch("app.tasks.collect_api._get_collector") as get:
        get.return_value.fetch_detail = AsyncMock(side_effect=ValueError("status=error"))
        resp = await client.get(f"/api/notices/{rows[f'ALIO-{t}1']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["attachments"] is None  # 조회 실패 — "조회함"으로 표시하지 않는다
