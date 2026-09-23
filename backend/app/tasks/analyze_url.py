"""AI URL 분석 Celery 태스크 — 실제 로직은 app.services.scraper_analysis.run_analysis."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.scraper_analysis import run_analysis
from app.tasks.celery_app import celery

logger = logging.getLogger("bidwatch.analyze_url")


async def _analyze(scraper_id: int) -> dict:
    # 워커 프로세스는 asyncio.run마다 루프가 새로 생기므로 엔진도 태스크마다 만든다
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return {"status": await run_analysis(scraper_id, factory)}
    finally:
        await engine.dispose()


@celery.task(name="app.tasks.analyze_url.analyze_url_task")
def analyze_url_task(scraper_id: int):
    """AI URL 분석 태스크. scraper_registry의 status를 analyzing → ready/failed로 전환."""
    return asyncio.run(_analyze(scraper_id))
