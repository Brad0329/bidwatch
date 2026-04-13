"""URL 구독 비즈니스 로직."""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scraper import ScraperRegistry, TenantSourceSubscription

logger = logging.getLogger("bidwatch.source")


async def find_or_create_scraper(
    url: str,
    url_hash: str,
    tenant_id: int,
    db: AsyncSession,
) -> tuple[ScraperRegistry, bool]:
    """URL로 기존 스크래퍼를 찾거나 새로 생성.

    Returns:
        (scraper, is_new)
    """
    result = await db.execute(
        select(ScraperRegistry).where(ScraperRegistry.url_hash == url_hash)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing, False

    scraper = ScraperRegistry(
        url=url,
        url_hash=url_hash,
        name=url,  # AI 분석 후 name이 업데이트됨
        status="pending",
        created_by_tenant_id=tenant_id,
    )
    db.add(scraper)
    await db.flush()
    return scraper, True


async def subscribe(
    tenant_id: int,
    scraper_id: int,
    db: AsyncSession,
) -> TenantSourceSubscription:
    """테넌트를 스크래퍼에 구독시킴. 이미 구독 중이면 재활성화."""
    result = await db.execute(
        select(TenantSourceSubscription).where(
            TenantSourceSubscription.tenant_id == tenant_id,
            TenantSourceSubscription.scraper_id == scraper_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if not existing.is_active:
            existing.is_active = True
            await _update_subscriber_count(scraper_id, 1, db)
        return existing

    sub = TenantSourceSubscription(
        tenant_id=tenant_id,
        scraper_id=scraper_id,
    )
    db.add(sub)
    await _update_subscriber_count(scraper_id, 1, db)
    await db.flush()
    return sub


async def unsubscribe(
    subscription_id: int,
    tenant_id: int,
    db: AsyncSession,
) -> None:
    """구독 비활성화 + subscriber_count 감소."""
    result = await db.execute(
        select(TenantSourceSubscription).where(
            TenantSourceSubscription.id == subscription_id,
            TenantSourceSubscription.tenant_id == tenant_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise ValueError("Subscription not found")

    if sub.is_active:
        sub.is_active = False
        await _update_subscriber_count(sub.scraper_id, -1, db)


async def _update_subscriber_count(scraper_id: int, delta: int, db: AsyncSession):
    """subscriber_count를 원자적으로 업데이트."""
    await db.execute(
        update(ScraperRegistry)
        .where(ScraperRegistry.id == scraper_id)
        .values(subscriber_count=ScraperRegistry.subscriber_count + delta)
    )
