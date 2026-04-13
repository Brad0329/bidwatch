"""Track 2: 스크래퍼 수집 태스크."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.scraper import ScraperRegistry
from app.services.collection import upsert_scraped_notices
from app.tasks.celery_app import celery

logger = logging.getLogger("bidwatch.collect_scraper")


async def _collect_single_scraper(scraper_id: int, config: dict, name: str):
    """단일 스크래퍼 수집."""
    from bid_collectors import GenericScraper

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        scraper = GenericScraper(config)
        logger.info(f"[Scraper:{name}] 수집 시작")

        result = await scraper.collect(days=30)
        logger.info(
            f"[Scraper:{name}] 수집 완료: "
            f"{result.total_after_dedup}건, {result.duration_seconds}초"
        )

        async with session_factory() as db:
            upsert_result = await upsert_scraped_notices(result.notices, scraper_id, db)

            # Update scraper stats
            scraper_row = await db.get(ScraperRegistry, scraper_id)
            if scraper_row:
                scraper_row.last_collected_at = datetime.now(timezone.utc)
                scraper_row.last_collected_count = result.total_after_dedup
                await db.commit()

        return {
            "scraper": name,
            "collected": result.total_after_dedup,
            "duration": result.duration_seconds,
            "errors": result.errors,
        }
    except Exception as e:
        logger.error(f"[Scraper:{name}] 수집 실패: {e}")
        return {"scraper": name, "error": str(e)}
    finally:
        await engine.dispose()


@celery.task(name="app.tasks.collect_scraper.collect_scrapers_task")
def collect_scrapers_task():
    """subscriber_count > 0인 모든 활성 스크래퍼를 순차 수집."""
    return asyncio.run(_collect_all_scrapers())


async def _collect_all_scrapers():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(ScraperRegistry).where(
                ScraperRegistry.is_active.is_(True),
                ScraperRegistry.status == "ready",
                ScraperRegistry.subscriber_count > 0,
            )
        )
        scrapers = result.scalars().all()

    await engine.dispose()

    if not scrapers:
        logger.info("활성 스크래퍼 없음 — 스킵")
        return []

    results = []
    for scraper in scrapers:
        r = await _collect_single_scraper(scraper.id, scraper.scraper_config, scraper.name)
        results.append(r)

    return results
