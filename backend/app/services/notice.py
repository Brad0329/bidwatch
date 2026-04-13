import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import BidNotice, SystemSource

logger = logging.getLogger("bidwatch.notice")

SKIP_DETAIL_TYPES = {"nara"}


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
