"""공공 출처 묶음 — 입찰 공고 / 지원사업(선택 구독) (F-004, 2026-09-25 사용자 결정: 입찰 전문, 지원사업은 기본 꺼짐).

화면의 묶음 표시·"지원" 배지는 API의 category·source_category만 본다 — 그 값을 여기서 건다.
"""

import uuid

import pytest
from bid_collectors.models import Notice
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.database import get_session_factory
from app.models.notice import BidNotice, SystemSource
from app.services.collection import upsert_bid_notices

EXPECTED = {"nara": "bid", "nara_prespec": "bid", "alio": "bid",
            "kstartup": "support", "bizinfo": "support", "smes": "support", "subsidy24": "support"}


async def _tenant(client: AsyncClient) -> dict:
    resp = await client.post("/api/auth/register", json={
        "email": f"sc-{uuid.uuid4().hex[:8]}@example.com", "password": "password123", "name": "U", "company_name": "C"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_system_sources_have_category(client: AsyncClient):
    headers = await _tenant(client)
    sources = (await client.get("/api/sources/system", headers=headers)).json()
    got = {s["collector_type"]: s["category"] for s in sources}
    assert got == EXPECTED

    # 새 회사는 아무 출처도 구독하지 않은 채 시작한다 — 지원사업은 "기본 꺼짐"
    assert (await client.get("/api/sources/system/subscriptions", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_notice_source_category_in_list_and_detail(client: AsyncClient):
    t = uuid.uuid4().hex[:8]
    async with get_session_factory()() as db:
        ids = dict((await db.execute(select(SystemSource.collector_type, SystemSource.id))).all())
        await upsert_bid_notices([Notice(source="기업마당", bid_no=f"BIZINFO-{t}", title=f"{t} 지원 공고",
                                         organization="기관", url="https://bizinfo.go.kr")], ids["bizinfo"], db)
        await upsert_bid_notices([Notice(source="나라장터", bid_no=f"용역-{t}", title=f"{t} 입찰 공고",
                                         organization="기관", url="https://g2b.go.kr")], ids["nara"], db)
    try:
        headers = await _tenant(client)
        assert (await client.post("/api/keywords", json={"keyword": t}, headers=headers)).status_code == 201
        for ct in ("bizinfo", "nara"):
            assert (await client.post(f"/api/sources/system/{ids[ct]}/subscribe", headers=headers)).status_code == 200

        items = (await client.get("/api/notices", headers=headers)).json()["items"]
        assert {i["bid_no"]: i["source_category"] for i in items} == {f"BIZINFO-{t}": "support", f"용역-{t}": "bid"}

        # 전체 출처(입찰) / 전체 출처(지원) — 건수(total)도 묶음대로
        for cat, expected in (("bid", [f"용역-{t}"]), ("support", [f"BIZINFO-{t}"])):
            resp = (await client.get("/api/notices", params={"category": cat}, headers=headers)).json()
            assert [i["bid_no"] for i in resp["items"]] == expected
            assert resp["total"] == 1
        assert (await client.get("/api/notices", params={"category": "x"}, headers=headers)).status_code == 422

        support_id = next(i["id"] for i in items if i["bid_no"] == f"BIZINFO-{t}")
        detail = (await client.get(f"/api/notices/{support_id}", headers=headers)).json()
        assert detail["source_category"] == "support"
    finally:
        async with get_session_factory()() as db:
            await db.execute(delete(BidNotice).where(BidNotice.bid_no.contains(t)))
            await db.commit()
