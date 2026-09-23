"""URL 출처(스크래퍼) 수집 → scraped_notices 저장.

호출 경로:
- AI 분석이 ready로 끝난 직후 첫 수집 (scraper_analysis.run_analysis)
- Celery 정기 수집 app.tasks.collect_scraper (자체 엔진의 session_factory를 넘긴다)
"""

import logging

from bid_collectors import GenericScraper
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_session_factory
from app.models.scraper import ScraperRegistry
from app.services.collection import upsert_scraped_notices
from app.services.url_guard import assert_safe_url, guard_request

logger = logging.getLogger("bidwatch.scraper_collection")

INITIAL_COLLECT_DAYS = 30  # 새로 추가한 사이트의 첫 수집 범위 — 추가하자마자 최근 공고가 보이게


def clean_title(title: str) -> str:
    """게시판 HTML의 비분리 공백(\\xa0 등)·연속 공백을 보통 공백 하나로.

    실측(2026-09-23 강원관광재단): 제목이 '운영\\xa0대행용역'으로 저장돼 키워드 '운영 대행'의 ILIKE 매칭에서 빠졌다.
    """
    return " ".join((title or "").split())


async def collect_scraper(
    scraper_id: int,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    days: int = INITIAL_COLLECT_DAYS,
) -> dict:
    """ready 스크래퍼 하나를 수집해 저장한다. 예외를 던지지 않고 결과 dict로 돌려준다
    ({"status": "ok"|"skipped"|"error", ...}) — 백그라운드·정기 작업에서 호출되기 때문."""
    factory = session_factory or get_session_factory()
    async with factory() as db:
        scraper = await db.get(ScraperRegistry, scraper_id)
        if scraper is None or scraper.status != "ready" or not scraper.scraper_config:
            state = "없음" if scraper is None else scraper.status
            logger.warning(f"[collect] scraper {scraper_id} 수집 건너뜀 (상태: {state})")
            return {"status": "skipped", "reason": state}
        config, name = dict(scraper.scraper_config), scraper.name

    try:
        # 설정 URL은 먼저 확인해 명시적 error로 끝낸다. 리다이렉트 등 실제 요청은 guard_request 훅이 막는다
        # (훅이 막으면 예외가 아니라 errors + 0건으로 돌아온다 — bid-collectors v1.1)
        for key in ("list_url", "session_init_url"):
            if config.get(key):
                await assert_safe_url(config[key])
        result = await GenericScraper(config, event_hooks={"request": [guard_request]}).collect(days=days)
    except Exception as e:
        logger.warning(f"[collect] {name}(scraper={scraper_id}) 수집 실패: {e}",
                       exc_info=not isinstance(e, ValueError))
        return {"status": "error", "error": str(e)}

    if result.errors and not result.notices:
        # 1페이지부터 실패(사이트 장애·차단된 요청) — "공고 없음"과 구분해 last_collected_*를 0으로 덮지 않는다
        logger.warning(f"[collect] {name}(scraper={scraper_id}) 수집 실패(0건): errors={result.errors[:3]}")
        return {"status": "error", "error": "; ".join(result.errors[:3]), "errors": result.errors}
    if result.errors or result.is_partial:
        # max_pages 상한 절단 또는 N페이지 실패 — 받은 만큼 저장하고 사실을 남긴다
        logger.warning(f"[collect] {name}(scraper={scraper_id}) 부분 수집: "
                       f"{len(result.notices)}건, partial={result.is_partial}, errors={result.errors[:3]}")

    notices = [n.model_copy(update={"title": clean_title(n.title)}) for n in result.notices]
    async with factory() as db:
        saved = await upsert_scraped_notices(notices, scraper_id, db)
        row = await db.get(ScraperRegistry, scraper_id)
        if row is not None:
            # DB가 시각을 찍게 한다. 실제 컬럼은 timestamptz인데 모델은 timezone 없는 DateTime이라
            # aware 값은 저장 실패, naive utcnow()는 세션 TimeZone(Asia/Seoul)으로 해석돼 9시간 이르게 저장된다
            # (2026-09-23 test_ready_analysis_collects_and_saves_immediately로 둘 다 확인)
            row.last_collected_at = func.now()
            row.last_collected_count = len(result.notices)
            await db.commit()

    logger.info(f"[collect] {name}(scraper={scraper_id}) {len(result.notices)}건 저장 (최근 {days}일)")
    return {"status": "ok", "collected": len(result.notices), "saved": saved["total"],
            "errors": result.errors, "partial": result.is_partial}
