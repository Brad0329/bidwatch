"""Track 2: 스크래퍼 정기 수집 Celery 태스크 — 실제 로직은 app.services.scraper_collection."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.scraper import ScraperRegistry
from app.services.scraper_collection import collect_scraper
from app.tasks.celery_app import celery

logger = logging.getLogger("bidwatch.collect_scraper")


@celery.task(name="app.tasks.collect_scraper.collect_scrapers_task")
def collect_scrapers_task():
    """subscriber_count > 0인 모든 활성 스크래퍼를 순차 수집."""
    return asyncio.run(_collect_all_scrapers())


async def _collect_all_scrapers():
    # 워커 프로세스는 asyncio.run마다 루프가 새로 생기므로 엔진도 태스크마다 만든다
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as db:
            scraper_ids = (await db.execute(
                select(ScraperRegistry.id).where(
                    ScraperRegistry.is_active.is_(True),
                    ScraperRegistry.status == "ready",
                    ScraperRegistry.subscriber_count > 0,
                )
            )).scalars().all()

        if not scraper_ids:
            logger.info("활성 스크래퍼 없음 — 스킵")
            return []
        return [await collect_scraper(sid, factory, days=30) for sid in scraper_ids]
    finally:
        await engine.dispose()
