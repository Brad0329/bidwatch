"""스크래퍼 AI 분석 실행 — 상태 전이(pending → analyzing → ready/failed)를 DB에 반영한다.

호출 경로 두 가지가 같은 함수를 쓴다:
- 접수 직후 FastAPI BackgroundTasks (Redis 없이 바로 실행)
- Celery 태스크 app.tasks.analyze_url (자체 엔진의 session_factory를 넘긴다)
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_session_factory
from app.models.scraper import ScraperRegistry
from app.services import scraper_ai

logger = logging.getLogger("bidwatch.scraper_analysis")


async def run_analysis(
    scraper_id: int,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> str:
    """분석을 실행하고 최종 상태("ready"/"failed"/"missing")를 돌려준다. 예외를 밖으로 던지지 않는다
    — 백그라운드 작업이라 던지면 아무도 못 본다. 실패는 status=failed + analysis_log + 로그로 남긴다."""
    factory = session_factory or get_session_factory()
    async with factory() as db:
        scraper = await db.get(ScraperRegistry, scraper_id)
        if scraper is None:
            logger.error(f"[analysis] scraper {scraper_id} 없음 — 분석을 건너뜀")
            return "missing"
        url = scraper.url
        scraper.status = "analyzing"
        await db.commit()

    # AI 호출·시험 수집은 수십 초~분 단위 — 그동안 DB 연결을 잡고 있지 않는다
    try:
        config, error = await scraper_ai.analyze_url(url), None
    except Exception as e:
        config, error = None, e
        logger.warning(f"[analysis] 실패 scraper={scraper_id} {url}: {e}",
                       exc_info=not isinstance(e, ValueError))

    async with factory() as db:
        scraper = await db.get(ScraperRegistry, scraper_id)
        if scraper is None:
            logger.error(f"[analysis] 분석 중 scraper {scraper_id}가 사라짐 — 결과를 버림")
            return "missing"
        if error is not None:
            scraper.status = "failed"
            scraper.analysis_log = str(error)
        else:
            scraper.scraper_config = config
            scraper.name = config.get("name") or scraper.name
            scraper.status = "ready"
            scraper.analysis_log = None
        await db.commit()

    if error is None:
        logger.info(f"[analysis] 완료 scraper={scraper_id} {config.get('name')}")
        return "ready"
    return "failed"
