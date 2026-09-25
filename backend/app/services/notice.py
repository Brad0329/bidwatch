import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import BidNotice, SystemSource
from app.schemas.notice import RelatedNotice

logger = logging.getLogger("bidwatch.notice")

SKIP_DETAIL_TYPES = {"nara"}


async def find_related(notice: BidNotice, source: SystemSource, db: AsyncSession) -> list[RelatedNotice]:
    """사전규격 ↔ 본 공고 연결 (F-018). 구독 여부와 무관하게 공유 데이터에서 찾는다(사전규격도 구독 무관, F-008).

    - 본 공고(nara): extra.bfSpecRgstNo → 사전규격 bid_no `사전규격-{업무}-{번호}` (업무 = 본 공고 bid_no 접두사).
      사전규격 bid_no가 refNo로 만들어진 행은 이 번호로 못 찾는다(bid-collectors 규칙).
    - 사전규격(nara_prespec): 그 사전규격을 bfSpecRgstNo로 가리키는 본 공고 ∪ extra.bidNtceNoList의 공고 — 최신 차수만.
    """
    extra = notice.extra or {}
    spec_no = extra.get("bfSpecRgstNo")
    if source.collector_type == "nara":
        if not spec_no:
            return []
        bid_type = notice.bid_no.split("-", 1)[0]
        rows = (await db.execute(
            select(BidNotice).join(SystemSource, SystemSource.id == BidNotice.source_id).where(
                SystemSource.collector_type == "nara_prespec",
                BidNotice.bid_no == f"사전규격-{bid_type}-{spec_no}",
            )
        )).scalars().all()
        kind = "prespec"
    elif source.collector_type == "nara_prespec":
        listed = [s.strip() for s in str(extra.get("bidNtceNoList") or "").split(",") if s.strip()]
        conds = []
        if spec_no:
            # 반대 방향(본 공고 → 사전규격)과 같게 업무 구분까지 맞춘다 — 사전규격 bid_no `사전규격-{업무}-{번호}`
            bid_type = notice.bid_no.split("-")[1] if notice.bid_no.count("-") >= 2 else ""
            conds.append(and_(BidNotice.extra["bfSpecRgstNo"].astext == str(spec_no),
                              BidNotice.bid_no.startswith(f"{bid_type}-")))
        if listed:
            conds.append(BidNotice.extra["bidNtceNo"].astext.in_(listed))
        if not conds:
            return []
        rows = (await db.execute(
            select(BidNotice).join(SystemSource, SystemSource.id == BidNotice.source_id).where(
                SystemSource.collector_type == "nara", BidNotice.superseded.is_(False), or_(*conds),
            ).order_by(BidNotice.start_date.desc().nulls_last(), BidNotice.id)
        )).scalars().all()
        kind = "notice"
    else:
        return []
    return [RelatedNotice(id=r.id, kind=kind, bid_no=r.bid_no, title=r.title, status=r.status) for r in rows]


async def enrich_notice_detail(
    notice: BidNotice, source: SystemSource, db: AsyncSession
) -> None:
    """content가 비어있으면 bid-collectors fetch_detail로 보충 후 DB에 저장."""
    if notice.content or source.collector_type in SKIP_DETAIL_TYPES:
        return

    detail = await _fetch_detail_via_collector(source.collector_type, notice.bid_no)
    if not detail:
        return

    if detail.get("content"):
        notice.content = detail["content"]

    # extra 병합
    extra = dict(notice.extra or {})
    for key, val in detail.items():
        if key not in ("content", "attachments") and val and not extra.get(key):
            extra[key] = val
    notice.extra = extra

    # 추가 첨부파일 병합
    if detail.get("attachments"):
        existing = notice.attachments or []
        existing_urls = {a["url"] for a in existing}
        for att in detail["attachments"]:
            if att["url"] not in existing_urls:
                existing.append(att)
        notice.attachments = existing

    if detail.get("apply_url") and not notice.detail_url:
        notice.detail_url = detail["apply_url"]

    await db.commit()


async def _fetch_detail_via_collector(collector_type: str, bid_no: str) -> dict | None:
    """bid-collectors 패키지의 fetch_detail을 호출."""
    from app.tasks.collect_api import _get_collector

    try:
        collector = _get_collector(collector_type)
        return await collector.fetch_detail(bid_no)
    except Exception:
        logger.warning(f"fetch_detail 실패: {collector_type}/{bid_no}", exc_info=True)
        return None
