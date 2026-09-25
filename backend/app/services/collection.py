"""수집 결과를 DB에 저장하는 서비스."""

import logging

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import BidNotice, SystemSource
from app.models.scraper import ScrapedNotice
from app.services.region import normalize_region, notice_region

logger = logging.getLogger("bidwatch.collection")

# 나라장터 공고종류(extra.ntceKindNm) 중 취소 — bidwatch가 원문으로 판정한다 (F-017, 2026-09-25 사용자 결정)
CANCEL_KIND = "취소공고"


def _status(notice) -> str:
    if (notice.extra or {}).get("ntceKindNm") == CANCEL_KIND:
        return "cancelled"
    return notice.status


# 차수 판정은 extra 원문(bidNtceNo·bidNtceOrd)으로. 행을 한 번 읽어 파이썬에서 계산하고 바뀐 행만 id로 고친다
# — SQL 한 문장(CTE+UPDATE)은 플래너가 JSONB 조건을 1행으로 오판해 중첩 루프로 20초 걸렸다(6천 행 실측).
_REVISION_ROWS = """
    SELECT id, extra->>'bidNtceNo' AS no, extra->>'bidNtceOrd' AS ord,
           extra->>'ntceKindNm' AS kind, status, superseded
    FROM bid_notices WHERE source_id = :sid AND extra ? 'bidNtceNo'
"""


async def refresh_revisions(source_id: int, db: AsyncSession) -> dict:
    """나라장터 차수 정리 — 수집 저장 직후 출처 전체를 다시 계산한다(재수집이 status를 덮어도 되살아난다).

    1. 같은 공고번호에 더 높은 차수가 있으면 superseded (차수는 정수 비교: "009" < "010")
    2. 취소공고 차수와 같거나 낮은 차수는 status=cancelled — 취소 뒤 더 높은 차수(재공고)는 그대로
    3. 이전 차수에 달린 태그 → 최신 차수로. 높은 차수의 태그부터 옮기고, 최신 차수에 그 회사 태그가
       이미 있으면 옮기지 않는다(공고당 태그 1개 — tenant_tags UNIQUE)
    extra에 bidNtceNo가 없는 출처는 대상 행이 없다. 차수가 숫자가 아닌 행은 판정에서 빼고 경고를 남긴다.
    """
    groups: dict[str, list] = {}
    bad_ord = 0
    for row in (await db.execute(text(_REVISION_ROWS), {"sid": source_id})).all():
        if not (row.ord or "").isdigit():
            bad_ord += 1
            continue
        groups.setdefault(row.no, []).append(row)

    to_supersede, to_unsupersede, to_cancel = [], [], []
    moves: list[tuple[list[int], int]] = []  # (이전 차수 id들 — 높은 차수부터, 최신 차수 id)
    for rows in groups.values():
        rows.sort(key=lambda r: int(r.ord), reverse=True)
        latest = rows[0]
        cancel_ord = max((int(r.ord) for r in rows if r.kind == CANCEL_KIND), default=None)
        for r in rows:
            should = r is not latest
            if should != r.superseded:
                (to_supersede if should else to_unsupersede).append(r.id)
            if cancel_ord is not None and int(r.ord) <= cancel_ord and r.status != "cancelled":
                to_cancel.append(r.id)
        if len(rows) > 1:
            moves.append(([r.id for r in rows[1:]], latest.id))

    for ids, value in ((to_supersede, True), (to_unsupersede, False)):
        if ids:
            await db.execute(text("UPDATE bid_notices SET superseded = :v WHERE id = ANY(:ids)"),
                             {"v": value, "ids": ids})
    if to_cancel:
        await db.execute(text("UPDATE bid_notices SET status = 'cancelled' WHERE id = ANY(:ids)"),
                         {"ids": to_cancel})

    moved = 0
    if moves:
        old_ids = [i for ids, _ in moves for i in ids]
        tags = (await db.execute(text(
            "SELECT id, tenant_id, notice_id FROM tenant_tags WHERE notice_type = 'bid' AND notice_id = ANY(:ids)"),
            {"ids": old_ids + [latest for _, latest in moves]})).all()
        taken = {(t.tenant_id, t.notice_id) for t in tags}
        by_notice: dict[int, list] = {}
        for t in tags:
            by_notice.setdefault(t.notice_id, []).append(t)
        for ids, latest_id in moves:
            for old_id in ids:  # 높은 차수부터
                for t in by_notice.get(old_id, []):
                    if (t.tenant_id, latest_id) in taken:
                        continue
                    await db.execute(text("UPDATE tenant_tags SET notice_id = :nid WHERE id = :id"),
                                     {"nid": latest_id, "id": t.id})
                    taken.add((t.tenant_id, latest_id))
                    moved += 1
    await db.commit()

    superseded = len(to_supersede) + len(to_unsupersede)
    cancelled = len(to_cancel)

    if bad_ord:
        logger.warning(f"[source {source_id}] 차수가 숫자가 아닌 공고 {bad_ord}건 — 차수 정리에서 뺐다")
    result = {"superseded_changed": superseded, "cancelled": cancelled, "tags_moved": moved}
    if superseded or cancelled or moved:
        logger.info(f"[source {source_id}] 차수 정리: {result}")
    return result


async def upsert_bid_notices(
    notices: list,
    source_id: int,
    db: AsyncSession,
) -> dict:
    """bid_collectors Notice 리스트를 bid_notices 테이블에 UPSERT.

    Returns:
        {"new": int, "updated": int, "total": int}
    """
    if not notices:
        return {"new": 0, "updated": 0, "total": 0}

    new_count = 0
    updated_count = 0

    for notice in notices:
        values = {
            "source_id": source_id,
            "bid_no": notice.bid_no,
            "title": notice.title,
            "organization": notice.organization,
            "start_date": notice.start_date,
            "end_date": notice.end_date,
            "status": _status(notice),
            "url": notice.url,
            "detail_url": notice.detail_url,
            "content": notice.content,
            "budget": notice.budget,
            "region": notice_region(notice.region, notice.extra),
            "category": notice.category,
            "attachments": [a for a in notice.attachments] if notice.attachments else None,
            "extra": notice.extra,
        }

        stmt = insert(BidNotice).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "bid_no"],
            set_={
                "title": stmt.excluded.title,
                "organization": stmt.excluded.organization,
                "start_date": stmt.excluded.start_date,
                "end_date": stmt.excluded.end_date,
                "status": stmt.excluded.status,
                "url": stmt.excluded.url,
                "detail_url": stmt.excluded.detail_url,
                "content": stmt.excluded.content,
                "budget": stmt.excluded.budget,
                "region": stmt.excluded.region,
                "category": stmt.excluded.category,
                "attachments": stmt.excluded.attachments,
                "extra": stmt.excluded.extra,
                "updated_at": func.now(),  # DB가 찍는다 — utcnow()는 9시간 이르게 저장됐다(SCHEMA.md)
            },
        )

        await db.execute(stmt)
        # rowcount == 1 for both insert and update with ON CONFLICT
        # Check if it was an insert by checking xmax
        new_count += 1  # simplified — count all as processed

    # 커밋은 차수 정리가 한다 — 한 트랜잭션이어야 upsert가 덮은 status(취소)가 정리 실패로 풀린 채 남지 않는다
    await refresh_revisions(source_id, db)

    return {"new": new_count, "updated": updated_count, "total": len(notices)}


async def upsert_scraped_notices(
    notices: list,
    scraper_id: int,
    db: AsyncSession,
) -> dict:
    """GenericScraper Notice 리스트를 scraped_notices 테이블에 UPSERT."""
    if not notices:
        return {"new": 0, "updated": 0, "total": 0}

    count = 0
    for notice in notices:
        values = {
            "scraper_id": scraper_id,
            "bid_no": notice.bid_no,
            "title": notice.title,
            "organization": notice.organization,
            "start_date": notice.start_date,
            "end_date": notice.end_date,
            "status": notice.status,
            "url": notice.url,
            "detail_url": notice.detail_url,
            "content": notice.content,
            "budget": notice.budget,
            "region": normalize_region(notice.region),
            "attachments": [a for a in notice.attachments] if notice.attachments else None,
            "extra": notice.extra,
        }

        stmt = insert(ScrapedNotice).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scraper_id", "bid_no"],
            set_={
                "title": stmt.excluded.title,
                "organization": stmt.excluded.organization,
                "start_date": stmt.excluded.start_date,
                "end_date": stmt.excluded.end_date,
                "status": stmt.excluded.status,
                "url": stmt.excluded.url,
                "detail_url": stmt.excluded.detail_url,
                "content": stmt.excluded.content,
                "budget": stmt.excluded.budget,
                "region": stmt.excluded.region,
                "attachments": stmt.excluded.attachments,
                "extra": stmt.excluded.extra,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    return {"new": count, "updated": 0, "total": len(notices)}


async def update_source_stats(
    source_id: int,
    count: int,
    db: AsyncSession,
) -> None:
    """system_sources의 수집 통계를 업데이트."""
    source = await db.get(SystemSource, source_id)
    if source:
        source.last_collected_at = func.now()
        source.last_collected_count = count
        await db.commit()
