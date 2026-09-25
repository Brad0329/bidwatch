"""차수 정리·취소(F-017 — 나라장터·국방·LH·가스공사)·공사 지역(F-011)·사전규격 연결(F-018).

수집 저장 경로(upsert_bid_notices → refresh_revisions)를 실제 DB로 통과시킨다. 공유 테이블에 넣은 행과
태그는 끝나면 지운다 — 테스트가 개발 DB를 쓴다. 공고번호에 token을 넣어 실제 공고와 섞이지 않게 한다.
"""

import uuid

import pytest
import pytest_asyncio
from bid_collectors.models import Notice
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.database import get_session_factory
from app.models.notice import BidNotice, SystemSource
from app.models.tag import TenantTag
from app.services.collection import upsert_bid_notices


def _nara(token: str, no: str, ord_: str, kind: str = "등록공고", bid_type: str = "용역", **extra) -> Notice:
    ntce_no = f"T{token}{no}"
    return Notice(
        source="나라장터", bid_no=f"{bid_type}-{ntce_no}-{ord_}", title=f"{token} 공고 {no} {ord_}",
        organization="어느기관", url="https://example.go.kr/n", region=extra.pop("region", ""),
        extra={"bidNtceNo": ntce_no, "bidNtceOrd": ord_, "ntceKindNm": kind, **extra},
    )


@pytest_asyncio.fixture
async def store(client: AsyncClient):
    """upsert_bid_notices로 저장하는 헬퍼. 끝나면 token이 든 행·태그를 지운다.
    client에 기대는 이유: client 픽스처가 테스트마다 DB 엔진을 새 이벤트 루프로 다시 만든다."""
    tokens: list[str] = []

    async def save(collector_type: str, notices: list[Notice]) -> None:
        async with get_session_factory()() as db:
            sid = await db.scalar(select(SystemSource.id).where(SystemSource.collector_type == collector_type))
            await upsert_bid_notices(notices, sid, db)

    async def rows(token: str) -> dict[str, BidNotice]:
        async with get_session_factory()() as db:
            found = (await db.execute(select(BidNotice).where(BidNotice.bid_no.contains(token)))).scalars().all()
            return {n.bid_no: n for n in found}

    def new_token() -> str:
        tokens.append(uuid.uuid4().hex[:8])
        return tokens[-1]

    yield save, rows, new_token

    async with get_session_factory()() as db:
        for t in tokens:
            ids = select(BidNotice.id).where(BidNotice.bid_no.contains(t))
            await db.execute(delete(TenantTag).where(TenantTag.notice_type == "bid", TenantTag.notice_id.in_(ids)))
            await db.execute(delete(BidNotice).where(BidNotice.bid_no.contains(t)))
        await db.commit()


@pytest.mark.asyncio
async def test_cancel_notice_cancels_earlier_revisions(store):
    save, rows, new_token = store
    t = new_token()
    await save("nara", [_nara(t, "A", "000"), _nara(t, "A", "001", "취소공고"), _nara(t, "A", "002", "재공고")])

    r = await rows(t)
    assert r[f"용역-T{t}A-000"].status == "cancelled"
    assert r[f"용역-T{t}A-001"].status == "cancelled"
    assert r[f"용역-T{t}A-002"].status == "ongoing"  # 취소 뒤 재공고는 살아 있다


@pytest.mark.asyncio
async def test_superseded_marks_earlier_revisions(store, caplog):
    save, rows, new_token = store
    t = new_token()
    # 차수는 정수로 비교한다 — 자릿수가 달라도 "10"이 "9"보다 높다(문자열 비교면 거꾸로)
    await save("nara", [_nara(t, "A", "9"), _nara(t, "A", "10", "변경공고"), _nara(t, "B", "000"),
                        _nara(t, "B", "x1", "변경공고")])  # 숫자 아닌 차수 — 판정에서 빠지고 경고

    r = await rows(t)
    assert r[f"용역-T{t}A-9"].superseded is True
    assert r[f"용역-T{t}A-10"].superseded is False
    assert r[f"용역-T{t}B-000"].superseded is False
    assert r[f"용역-T{t}B-x1"].superseded is False
    assert "차수가 숫자가 아닌 공고" in caplog.text


@pytest.mark.asyncio
async def test_recollect_keeps_revision_flags(store):
    save, rows, new_token = store
    t = new_token()
    await save("nara", [_nara(t, "A", "000"), _nara(t, "A", "001", "취소공고")])
    # 재수집: 원 공고(000)가 status=ongoing으로 다시 upsert된다
    await save("nara", [_nara(t, "A", "000")])

    r = await rows(t)
    assert r[f"용역-T{t}A-000"].status == "cancelled"
    assert r[f"용역-T{t}A-000"].superseded is True


def _d2b(token: str, key: str, ord_: int, kind: str | None = "정상공고", **extra) -> Notice:
    extra = {"pblancOdr": str(ord_), **({"pblancSe": kind} if kind else {}), **extra}
    return Notice(source="국방전자조달", bid_no=f"D2B-국내경쟁-T{token}{key}-{ord_}", title=f"{token} 국방 {key} {ord_}",
                  organization="국군어느부대", url="https://www.d2b.go.kr/", extra=extra)


@pytest.mark.asyncio
async def test_d2b_revisions_and_cancel(store):
    """국방은 정정·취소가 차수(pblancOdr)를 올려 새 행으로 온다 — 나라장터와 같이 최신 차수만, 취소는 낮은 차수까지."""
    save, rows, new_token = store
    t = new_token()
    await save("d2b", [
        _d2b(t, "A", 1), _d2b(t, "A", 2, "취소공고"),
        _d2b(t, "B", 1), _d2b(t, "B", 2, "정정공고"),
        _d2b(t, "C", 1, None, progrsSttus="진행중"),  # 수의 목록 — pblancSe 없음
        _d2b(t, "D", 1, None, progrsSttus="진행중"), _d2b(t, "D", 2, None, progrsSttus="공개협상취소"),  # 수의 취소
    ])
    r = await rows(t)
    a1, a2 = r[f"D2B-국내경쟁-T{t}A-1"], r[f"D2B-국내경쟁-T{t}A-2"]
    b1, b2 = r[f"D2B-국내경쟁-T{t}B-1"], r[f"D2B-국내경쟁-T{t}B-2"]
    assert (a1.superseded, a1.status, a2.superseded, a2.status) == (True, "cancelled", False, "cancelled")
    assert (b1.superseded, b1.status, b2.superseded, b2.status) == (True, "ongoing", False, "ongoing")
    assert (r[f"D2B-국내경쟁-T{t}C-1"].superseded, r[f"D2B-국내경쟁-T{t}C-1"].status) == (False, "ongoing")
    assert [r[f"D2B-국내경쟁-T{t}D-{o}"].status for o in (1, 2)] == ["cancelled", "cancelled"]


@pytest.mark.asyncio
async def test_institution_cancel_marks(store):
    """LH·가스공사는 같은 bid_no 행이 덮이며 취소가 원문 표시로만 온다 — 표시가 있으면 cancelled, 차수 정리 대상 아님."""
    save, rows, new_token = store
    t = new_token()

    def inst(prefix: str, key: str, **extra) -> Notice:
        return Notice(source=prefix, bid_no=f"{prefix}-T{t}{key}", title=f"{t} {prefix} {key}",
                      organization="어느공사", url="https://example.or.kr/n", extra=extra)

    await save("lh", [inst("LH", "A", bidKind="취소공고", bidDegree="01"), inst("LH", "B", bidKind="정정공고")])
    await save("kogas", [inst("KOGAS", "A", CANCEL_YN="취소"), inst("KOGAS", "B", NOTICE_CODE="x")])
    r = await rows(t)
    assert {k: (n.status, n.superseded) for k, n in r.items()} == {
        f"LH-T{t}A": ("cancelled", False), f"LH-T{t}B": ("ongoing", False),
        f"KOGAS-T{t}A": ("cancelled", False), f"KOGAS-T{t}B": ("ongoing", False),
    }


async def _tenant(client: AsyncClient, keyword: str) -> tuple[dict, int]:
    resp = await client.post("/api/auth/register", json={
        "email": f"rv-{uuid.uuid4().hex[:8]}@example.com", "password": "password123",
        "name": "U", "company_name": "C"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    assert (await client.post("/api/keywords", json={"keyword": keyword}, headers=headers)).status_code == 201
    async with get_session_factory()() as db:
        nara_id = await db.scalar(select(SystemSource.id).where(SystemSource.collector_type == "nara"))
    assert (await client.post(f"/api/sources/system/{nara_id}/subscribe", headers=headers)).status_code == 200
    return headers, nara_id


@pytest.mark.asyncio
async def test_list_shows_latest_revision_only(client: AsyncClient, store):
    save, rows, new_token = store
    t = new_token()
    await save("nara", [
        _nara(t, "A", "000"), _nara(t, "A", "001", "변경공고"),      # A: 최신 001만
        _nara(t, "B", "000"), _nara(t, "B", "001", "취소공고"),      # B: 취소 — 기본 목록에서 빠진다
    ])
    headers, _ = await _tenant(client, t)

    default = (await client.get("/api/notices", headers=headers)).json()
    assert [i["bid_no"] for i in default["items"]] == [f"용역-T{t}A-001"]
    assert default["total"] == 1

    cancelled = (await client.get("/api/notices", params={"status": "cancelled"}, headers=headers)).json()
    assert [i["bid_no"] for i in cancelled["items"]] == [f"용역-T{t}B-001"]

    # 태그 필터는 거르지 않는다 — 취소된 공고에 단 태그도 검토요청 화면에 보인다
    b1 = (await rows(t))[f"용역-T{t}B-001"]
    assert (await client.put("/api/tags", json={"notice_type": "bid", "notice_id": b1.id, "tag": "검토요청"},
                             headers=headers)).status_code in (200, 201)
    tagged = (await client.get("/api/notices", params={"tag": "검토요청"}, headers=headers)).json()
    assert [(i["bid_no"], i["status"]) for i in tagged["items"]] == [(f"용역-T{t}B-001", "cancelled")]


@pytest.mark.asyncio
async def test_tag_moves_to_latest_revision(client: AsyncClient, store):
    save, rows, new_token = store
    t = new_token()
    await save("nara", [_nara(t, "A", "000"), _nara(t, "B", "000"), _nara(t, "B", "001", "변경공고")])
    headers, _ = await _tenant(client, t)
    r = await rows(t)
    for bid_no, tag in ((f"용역-T{t}A-000", "검토요청"), (f"용역-T{t}B-000", "검토요청"), (f"용역-T{t}B-001", "입찰대상")):
        assert (await client.put("/api/tags", json={"notice_type": "bid", "notice_id": r[bid_no].id, "tag": tag},
                                 headers=headers)).status_code in (200, 201)

    # A에 새 차수가 온다 → 000의 태그가 001로 옮겨간다 / B는 최신 차수에 이미 태그가 있어 옮기지 않는다
    await save("nara", [_nara(t, "A", "001", "변경공고")])
    r = await rows(t)
    async with get_session_factory()() as db:
        tags = dict((await db.execute(select(TenantTag.notice_id, TenantTag.tag).where(
            TenantTag.notice_type == "bid", TenantTag.notice_id.in_([n.id for n in r.values()])))).all())
    assert tags.get(r[f"용역-T{t}A-001"].id) == "검토요청"
    assert r[f"용역-T{t}A-000"].id not in tags
    assert tags.get(r[f"용역-T{t}B-001"].id) == "입찰대상"
    assert tags.get(r[f"용역-T{t}B-000"].id) == "검토요청"


@pytest.mark.asyncio
async def test_construction_region_uses_site(store):
    save, rows, new_token = store
    t = new_token()
    await save("nara", [
        _nara(t, "A", "000", bid_type="공사", region="경희대학교 국제캠퍼스", cnstrtsiteRgnNm="경기도 용인시 기흥구"),
        _nara(t, "B", "000", bid_type="용역", region="경상북도 남부건설사업소"),  # 현장 지역 없음 → 기존대로
    ])
    r = await rows(t)
    assert r[f"공사-T{t}A-000"].region == "경기"
    assert r[f"용역-T{t}B-000"].region == "경북"


@pytest.mark.asyncio
async def test_related_prespec_and_notice(client: AsyncClient, store):
    save, rows, new_token = store
    t = new_token()
    spec_no = f"S{t}"
    # 사전규격의 bidNtceNoList가 D를 가리킨다(D는 bfSpecRgstNo가 없다) — 두 경로의 합집합
    await save("nara_prespec", [Notice(
        source="나라장터", bid_no=f"사전규격-용역-{spec_no}", title=f"{t} 사전규격", organization="어느기관",
        url="https://www.g2b.go.kr", extra={"bfSpecRgstNo": spec_no, "bidNtceNoList": f"T{t}D, X-none"})])
    await save("nara", [
        _nara(t, "A", "000", bfSpecRgstNo=spec_no), _nara(t, "A", "001", "변경공고", bfSpecRgstNo=spec_no),
        _nara(t, "C", "000"),  # 사전규격 없음
        _nara(t, "D", "000"),
        _nara(t, "E", "000", bid_type="물품", bfSpecRgstNo=spec_no),  # 같은 번호라도 업무가 다르면 잇지 않는다
    ])
    headers, _ = await _tenant(client, t)
    r = await rows(t)

    notice = (await client.get(f"/api/notices/{r[f'용역-T{t}A-001'].id}", headers=headers)).json()
    assert [(x["kind"], x["bid_no"]) for x in notice["related"]] == [("prespec", f"사전규격-용역-{spec_no}")]

    spec = (await client.get(f"/api/notices/{r[f'사전규격-용역-{spec_no}'].id}", headers=headers)).json()
    assert sorted((x["kind"], x["bid_no"]) for x in spec["related"]) == [
        ("notice", f"용역-T{t}A-001"), ("notice", f"용역-T{t}D-000")]  # 최신 차수만, 물품 E는 빠진다

    other = (await client.get(f"/api/notices/{r[f'물품-T{t}E-000'].id}", headers=headers)).json()
    assert other["related"] == []  # 물품 사전규격은 없다

    alone = (await client.get(f"/api/notices/{r[f'용역-T{t}C-000'].id}", headers=headers)).json()
    assert alone["related"] == []
