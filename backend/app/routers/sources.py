import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_tenant, get_current_user, require_admin
from app.models.notice import SystemSource
from app.models.scraper import ScraperRegistry, TenantSourceSubscription
from app.models.subscription import TenantSystemSubscription
from app.models.tenant import Tenant, User
from app.schemas.source import (
    PreviewResponse,
    SourceAddRequest,
    SourceAddResponse,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    SystemSourceResponse,
)
from app.services.scraper_ai import hash_url, normalize_url
from app.services.scraper_analysis import run_analysis
from app.services.source import find_or_create_scraper, subscribe, unsubscribe
from app.services.url_guard import UnsafeUrlError, check_url_syntax, guard_request

logger = logging.getLogger("bidwatch.sources")

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _dispatch_analysis(background_tasks: BackgroundTasks, scraper_id: int):
    """AI 분석을 응답 뒤 백그라운드로 실행한다 (Redis·Celery 없이).

    서버가 분석 도중 재시작되면 status가 analyzing에 남는다 — 복구 경로는 plan.md 보류 항목.
    """
    background_tasks.add_task(run_analysis, scraper_id)


@router.get("/system", response_model=list[SystemSourceResponse])
async def list_system_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공공 API 소스 목록 + 수집 상태."""
    result = await db.execute(select(SystemSource).order_by(SystemSource.id))
    return result.scalars().all()


@router.get("/system/subscriptions")
async def list_system_subscriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내가 구독 중인 시스템 출처 ID 목록."""
    result = await db.execute(
        select(TenantSystemSubscription.system_source_id).where(
            TenantSystemSubscription.tenant_id == user.tenant_id
        )
    )
    return [row[0] for row in result.all()]


@router.post("/system/{source_id}/subscribe")
async def subscribe_system_source(
    source_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """시스템 출처 구독."""
    source = await db.get(SystemSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="출처를 찾을 수 없습니다")

    existing = await db.scalar(
        select(TenantSystemSubscription.id).where(
            TenantSystemSubscription.tenant_id == user.tenant_id,
            TenantSystemSubscription.system_source_id == source_id,
        )
    )
    if existing:
        return {"message": "이미 구독 중입니다"}

    sub = TenantSystemSubscription(
        tenant_id=user.tenant_id,
        system_source_id=source_id,
    )
    db.add(sub)
    await db.commit()
    return {"message": f"{source.name} 구독 완료"}


@router.delete("/system/{source_id}/unsubscribe")
async def unsubscribe_system_source(
    source_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """시스템 출처 구독 해제."""
    result = await db.execute(
        select(TenantSystemSubscription).where(
            TenantSystemSubscription.tenant_id == user.tenant_id,
            TenantSystemSubscription.system_source_id == source_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다")

    await db.delete(sub)
    await db.commit()
    return {"message": "구독 해제 완료"}


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """내 구독 목록."""
    result = await db.execute(
        select(TenantSourceSubscription, ScraperRegistry)
        .join(ScraperRegistry, TenantSourceSubscription.scraper_id == ScraperRegistry.id)
        .where(TenantSourceSubscription.tenant_id == tenant.id)
        .order_by(TenantSourceSubscription.id.desc())
    )
    rows = result.all()

    return [
        SubscriptionResponse(
            id=sub.id,
            scraper_id=scraper.id,
            scraper_name=scraper.name,
            scraper_status=scraper.status,
            scraper_url=scraper.url,
            custom_name=sub.custom_name,
            is_active=sub.is_active,
            last_collected_at=scraper.last_collected_at,
            last_collected_count=scraper.last_collected_count,
        )
        for sub, scraper in rows
    ]


@router.post("", response_model=SourceAddResponse)
async def add_source(
    req: SourceAddRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),  # 새 URL마다 AI 비용 — owner·admin만 (2026-09-23 결정)
    db: AsyncSession = Depends(get_db),
):
    """URL 제출 → 스크래퍼 확인/생성 → 즉시 구독 → (새 URL·실패 URL이면) AI 분석 백그라운드 실행."""
    normalized = normalize_url(req.url)
    try:
        check_url_syntax(normalized)
    except UnsafeUrlError as e:
        logger.warning(f"[sources] 거부한 URL (tenant={user.tenant_id}): {normalized} — {e}")
        raise HTTPException(status_code=400, detail="사용할 수 없는 URL입니다")

    scraper, is_new = await find_or_create_scraper(
        url=normalized,
        url_hash=hash_url(normalized),
        tenant_id=user.tenant_id,
        db=db,
    )
    # 분석 결과와 무관하게 제출한 회사를 바로 구독시킨다 — 분석이 끝나면 곧바로 이 회사 목록에 이어진다
    sub = await subscribe(user.tenant_id, scraper.id, db)

    retry = scraper.status == "failed" and not is_new
    if retry:
        scraper.status = "pending"
    await db.commit()

    if is_new or retry:
        _dispatch_analysis(background_tasks, scraper.id)

    messages = {
        "ready": f"'{scraper.name}' 사이트가 구독되었습니다.",
        "analyzing": "AI 분석이 진행 중입니다. 잠시 후 상태를 확인하세요.",
        "pending": ("이전 분석이 실패해 재분석을 시작합니다." if retry
                    else "AI 분석을 시작합니다. 잠시 후 상태를 확인하세요."),
    }
    return SourceAddResponse(
        scraper_id=scraper.id,
        subscription_id=sub.id,
        scraper_status=scraper.status,
        message=messages.get(scraper.status, "구독되었습니다."),
    )


@router.get("/{sub_id}", response_model=SubscriptionResponse)
async def get_subscription(
    sub_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """구독 상세 (폴링용 — 스크래퍼 상태 확인)."""
    result = await db.execute(
        select(TenantSourceSubscription, ScraperRegistry)
        .join(ScraperRegistry, TenantSourceSubscription.scraper_id == ScraperRegistry.id)
        .where(
            TenantSourceSubscription.id == sub_id,
            TenantSourceSubscription.tenant_id == tenant.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub, scraper = row
    return SubscriptionResponse(
        id=sub.id,
        scraper_id=scraper.id,
        scraper_name=scraper.name,
        scraper_status=scraper.status,
        scraper_url=scraper.url,
        custom_name=sub.custom_name,
        is_active=sub.is_active,
        last_collected_at=scraper.last_collected_at,
        last_collected_count=scraper.last_collected_count,
    )


@router.get("/{sub_id}/preview", response_model=PreviewResponse)
async def preview_scraper(
    sub_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """스크래퍼 테스트 수집 — 결과를 DB에 저장하지 않고 반환."""
    result = await db.execute(
        select(TenantSourceSubscription, ScraperRegistry)
        .join(ScraperRegistry, TenantSourceSubscription.scraper_id == ScraperRegistry.id)
        .where(
            TenantSourceSubscription.id == sub_id,
            TenantSourceSubscription.tenant_id == tenant.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub, scraper = row
    if scraper.status != "ready":
        raise HTTPException(status_code=400, detail=f"Scraper is not ready (status: {scraper.status})")

    from bid_collectors import GenericScraper

    try:
        gs = GenericScraper(scraper.scraper_config, event_hooks={"request": [guard_request]})
        collect_result = await gs.collect(days=30)
    except Exception as e:
        # 원인은 로그로만 — 응답에 예외 원문(내부 URL·경로)을 싣지 않는다
        logger.warning(f"[preview] scraper={scraper.id} 수집 예외: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="스크래핑 실패")
    if collect_result.errors and not collect_result.notices:
        # 1페이지부터 실패(사이트 장애·차단된 요청) — "공고 0건"으로 보이지 않게
        logger.warning(f"[preview] scraper={scraper.id} 요청 실패: {collect_result.errors[:3]}")
        raise HTTPException(status_code=502, detail="사이트에서 공고를 가져오지 못했습니다")

    notices_dicts = [n.model_dump(mode="json") for n in collect_result.notices[:20]]

    return PreviewResponse(
        scraper_name=scraper.name,
        notices_count=len(collect_result.notices),
        notices=notices_dicts,
    )


@router.post("/{sub_id}/confirm", response_model=SubscriptionResponse)
async def confirm_subscription(
    sub_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """미리보기 확인 후 구독 확정 (이미 구독 상태면 그대로 반환)."""
    result = await db.execute(
        select(TenantSourceSubscription, ScraperRegistry)
        .join(ScraperRegistry, TenantSourceSubscription.scraper_id == ScraperRegistry.id)
        .where(
            TenantSourceSubscription.id == sub_id,
            TenantSourceSubscription.tenant_id == tenant.id,
        )
    )
    row = result.one_or_none()
    if not row:
        # 아직 구독 안 됨 — scraper_id로 구독 생성 필요
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub, scraper = row
    if not sub.is_active:
        sub.is_active = True
        from app.services.source import _update_subscriber_count
        await _update_subscriber_count(scraper.id, 1, db)
        await db.commit()

    return SubscriptionResponse(
        id=sub.id,
        scraper_id=scraper.id,
        scraper_name=scraper.name,
        scraper_status=scraper.status,
        scraper_url=scraper.url,
        custom_name=sub.custom_name,
        is_active=sub.is_active,
        last_collected_at=scraper.last_collected_at,
        last_collected_count=scraper.last_collected_count,
    )


@router.patch("/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription(
    sub_id: int,
    req: SubscriptionUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """구독 수정 (별칭, 활성화/비활성화)."""
    result = await db.execute(
        select(TenantSourceSubscription, ScraperRegistry)
        .join(ScraperRegistry, TenantSourceSubscription.scraper_id == ScraperRegistry.id)
        .where(
            TenantSourceSubscription.id == sub_id,
            TenantSourceSubscription.tenant_id == tenant.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub, scraper = row

    if req.custom_name is not None:
        sub.custom_name = req.custom_name

    if req.is_active is not None and req.is_active != sub.is_active:
        from app.services.source import _update_subscriber_count
        delta = 1 if req.is_active else -1
        await _update_subscriber_count(scraper.id, delta, db)
        sub.is_active = req.is_active

    await db.commit()

    return SubscriptionResponse(
        id=sub.id,
        scraper_id=scraper.id,
        scraper_name=scraper.name,
        scraper_status=scraper.status,
        scraper_url=scraper.url,
        custom_name=sub.custom_name,
        is_active=sub.is_active,
        last_collected_at=scraper.last_collected_at,
        last_collected_count=scraper.last_collected_count,
    )


@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """구독 해지 (soft delete)."""
    await unsubscribe(sub_id, tenant.id, db)
    await db.commit()
    return {"message": "구독이 해지되었습니다"}
