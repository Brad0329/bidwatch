"""Track 1: 공공 API 수집 태스크."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.notice import SystemSource
from app.services.collection import update_source_stats, upsert_bid_notices

logger = logging.getLogger("bidwatch.collect_api")


def _get_celery():
    """Celery 인스턴스를 lazy import (미설치 시 에러 방지)."""
    from app.tasks.celery_app import celery
    return celery

# collector_type → bid_collectors 클래스 매핑
COLLECTOR_MAP = {
    "nara": ("bid_collectors.nara", "NaraCollector", "DATA_GO_KR_KEY"),
    "nara_prespec": ("bid_collectors.nara", "NaraCollector", "DATA_GO_KR_KEY"),
    "kstartup": ("bid_collectors.kstartup", "KstartupCollector", "DATA_GO_KR_KEY"),
    "bizinfo": ("bid_collectors.bizinfo", "BizinfoCollector", "BIZINFO_API_KEY"),
    "subsidy24": ("bid_collectors.subsidy24", "Subsidy24Collector", "DATA_GO_KR_KEY"),
    "smes": ("bid_collectors.smes", "SmesCollector", "DATA_GO_KR_KEY"),
}

# nara 수집 시 사전규격도 같이 수집
CHAINED_COLLECTORS = {
    "nara": "nara_prespec",
}


def _get_collector(collector_type: str):
    """collector_type에 해당하는 수집기 인스턴스를 생성."""
    import importlib

    if collector_type not in COLLECTOR_MAP:
        raise ValueError(f"Unknown collector_type: {collector_type}")

    module_path, class_name, env_key = COLLECTOR_MAP[collector_type]
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    api_key = getattr(settings, env_key, "") or ""
    return cls(api_key=api_key)


async def _collect_source(source_id: int, collector_type: str, days: int = 1):
    """단일 소스 수집 실행."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        collector = _get_collector(collector_type)

        if collector_type == "nara_prespec":
            # 사전규격: collect_pre_specs()는 list[Notice]를 반환
            label = "나라장터 사전규격"
            logger.info(f"[{label}] 수집 시작: days={days}")
            notices = await collector.collect_pre_specs(days=days)
            collected = len(notices)
            logger.info(f"[{label}] 수집 완료: {collected}건")

            async with session_factory() as db:
                upsert_result = await upsert_bid_notices(notices, source_id, db)
                await update_source_stats(source_id, collected, db)

            logger.info(f"[{label}] DB 저장: {upsert_result}")
            return {
                "source": label,
                "collected": collected,
                "duration": 0,
                "errors": [],
            }
        else:
            logger.info(f"[{collector.source_name}] 수집 시작: days={days}")

            result = await collector.collect(days=days)
            logger.info(
                f"[{collector.source_name}] 수집 완료: "
                f"{result.total_after_dedup}건, {result.pages_processed}페이지, "
                f"{result.duration_seconds}초"
            )

            if result.errors:
                logger.warning(f"[{collector.source_name}] 에러: {result.errors}")

            async with session_factory() as db:
                upsert_result = await upsert_bid_notices(result.notices, source_id, db)
                await update_source_stats(source_id, result.total_after_dedup, db)

            logger.info(f"[{collector.source_name}] DB 저장: {upsert_result}")
            return {
                "source": collector.source_name,
                "collected": result.total_after_dedup,
                "duration": result.duration_seconds,
                "errors": result.errors,
            }
    except Exception as e:
        logger.error(f"[{collector_type}] 수집 실패: {e}")
        return {"source": collector_type, "error": str(e)}
    finally:
        await engine.dispose()


def collect_public_api_task(days: int = 1):
    """모든 활성 시스템 소스를 순차 수집."""
    return asyncio.run(_collect_all_sources(days))


async def _collect_all_sources(days: int = 1):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(SystemSource).where(SystemSource.is_active.is_(True))
        )
        sources = result.scalars().all()

    await engine.dispose()

    results = []
    for source in sources:
        r = await _collect_source(source.id, source.collector_type, days)
        results.append(r)

    return results


def collect_single_source_task(source_id: int, collector_type: str, days: int = 1):
    """단일 소스 수집 (수동 실행용)."""
    return asyncio.run(_collect_source(source_id, collector_type, days))


# Celery 태스크 등록 (Celery 설치 시에만)
try:
    _celery = _get_celery()
    collect_public_api_task = _celery.task(
        name="app.tasks.collect_api.collect_public_api_task"
    )(collect_public_api_task)
    collect_single_source_task = _celery.task(
        name="app.tasks.collect_api.collect_single_source_task"
    )(collect_single_source_task)
except ImportError:
    pass
