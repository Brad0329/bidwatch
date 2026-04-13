from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.notice import BidNotice, SystemSource
from app.models.scraper import ScraperRegistry, ScrapedNotice
from app.models.tenant import User
from app.schemas.admin import CollectionRunRequest, CollectionRunResponse, SystemSourceResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/collection/status", response_model=list[SystemSourceResponse])
async def collection_status(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemSource).order_by(SystemSource.id))
    return result.scalars().all()


@router.post("/collection/run", response_model=CollectionRunResponse)
async def collection_run(
    req: CollectionRunRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if req.sync:
        # 동기 수집: Celery/Redis 없이 직접 실행
        from app.tasks.collect_api import _collect_source, _collect_all_sources, CHAINED_COLLECTORS

        if req.source_id:
            source = await db.get(SystemSource, req.source_id)
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")
            result = await _collect_source(source.id, source.collector_type, req.days)
            collected = result.get("collected", 0)
            error = result.get("error")
            if error:
                return CollectionRunResponse(
                    status="error",
                    message=f"{source.name} 수집 실패: {error}",
                )

            # 연쇄 수집 (예: nara → nara_prespec)
            chained_msg = ""
            chained_type = CHAINED_COLLECTORS.get(source.collector_type)
            if chained_type:
                chained_row = await db.execute(
                    select(SystemSource).where(SystemSource.collector_type == chained_type)
                )
                chained_source = chained_row.scalar_one_or_none()
                if chained_source:
                    chained_result = await _collect_source(
                        chained_source.id, chained_type, req.days
                    )
                    chained_collected = chained_result.get("collected", 0)
                    chained_error = chained_result.get("error")
                    if chained_error:
                        chained_msg = f" / {chained_source.name} 실패: {chained_error}"
                    else:
                        chained_msg = f" / {chained_source.name} {chained_collected}건"

            return CollectionRunResponse(
                status="completed",
                message=f"{source.name} 수집 완료: {collected}건{chained_msg}",
            )
        else:
            results = await _collect_all_sources(req.days)
            total = sum(r.get("collected", 0) for r in results)
            errors = [r for r in results if r.get("error")]
            msg = f"전체 수집 완료: {total}건"
            if errors:
                msg += f" (실패 {len(errors)}건)"
            return CollectionRunResponse(status="completed", message=msg)
    else:
        # 비동기 수집: Celery 태스크 디스패치
        if req.source_id:
            source = await db.get(SystemSource, req.source_id)
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            from app.tasks.collect_api import collect_single_source_task
            task = collect_single_source_task.delay(source.id, source.collector_type, req.days)
            return CollectionRunResponse(
                status="started",
                message=f"{source.name} 수집 시작",
                task_id=task.id,
            )
        else:
            from app.tasks.collect_api import collect_public_api_task
            task = collect_public_api_task.delay(req.days)
            return CollectionRunResponse(
                status="started",
                message="전체 공공 API 수집 시작",
                task_id=task.id,
            )


@router.get("/collection/stats")
async def collection_stats(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    bid_count = await db.scalar(select(func.count()).select_from(BidNotice))
    scraped_count = await db.scalar(select(func.count()).select_from(ScrapedNotice))
    scraper_count = await db.scalar(
        select(func.count()).select_from(ScraperRegistry).where(ScraperRegistry.status == "ready")
    )

    return {
        "bid_notices_count": bid_count or 0,
        "scraped_notices_count": scraped_count or 0,
        "active_scrapers_count": scraper_count or 0,
    }
