"""AI URL 분석 Celery 태스크."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.scraper import ScraperRegistry
from app.services.scraper_ai import analyze_url
from app.tasks.celery_app import celery

logger = logging.getLogger("bidwatch.analyze_url")


async def _analyze(scraper_id: int):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            scraper = await db.get(ScraperRegistry, scraper_id)
            if not scraper:
                logger.error(f"Scraper {scraper_id} not found")
                return {"error": "Scraper not found"}

            # 분석 중 상태로 변경
            scraper.status = "analyzing"
            await db.commit()

            try:
                config = await analyze_url(scraper.url)

                scraper.scraper_config = config
                scraper.name = config.get("name", scraper.name)
                scraper.status = "ready"
                scraper.analysis_log = None
                await db.commit()

                logger.info(f"[Scraper:{scraper.name}] AI 분석 완료")
                return {"status": "ready", "name": scraper.name}

            except Exception as e:
                scraper.status = "failed"
                scraper.analysis_log = str(e)
                await db.commit()

                logger.error(f"[Scraper:{scraper_id}] AI 분석 실패: {e}")
                return {"status": "failed", "error": str(e)}

    finally:
        await engine.dispose()


@celery.task(name="app.tasks.analyze_url.analyze_url_task")
def analyze_url_task(scraper_id: int):
    """AI URL 분석 태스크. scraper_registry의 status를 analyzing → ready/failed로 전환."""
    return asyncio.run(_analyze(scraper_id))
