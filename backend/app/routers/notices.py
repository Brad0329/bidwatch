from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, cast, func, literal, or_, select, tuple_, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.keyword import TenantKeyword
from app.models.notice import BidNotice, SystemSource
from app.models.scraper import ScrapedNotice, ScraperRegistry, TenantSourceSubscription
from app.models.subscription import TenantSystemSubscription
from app.models.tag import TenantTag
from app.models.tenant import User
from app.schemas.notice import BidNoticeResponse, NoticeListResponse
from app.services.region import REGIONS

router = APIRouter(prefix="/api/notices", tags=["notices"])


@router.get("/regions")
async def list_regions():
    """사용 가능한 지역 목록 반환."""
    return REGIONS


async def _build_tag_map(
    db: AsyncSession, tenant_id: int, notice_type: str, notice_ids: list[int]
) -> dict[int, str]:
    """공고 ID 목록에 대한 태그 맵 반환."""
    if not notice_ids:
        return {}
    result = await db.execute(
        select(TenantTag.notice_id, TenantTag.tag).where(
            TenantTag.tenant_id == tenant_id,
            TenantTag.notice_type == notice_type,
            TenantTag.notice_id.in_(notice_ids),
        )
    )
    return {row[0]: row[1] for row in result.all()}


def _merged_notices_subquery(tenant_id: int, system_source_ids: list[int]):
    """구독한 공공 출처 공고(bid_notices) + 구독한 URL 출처 공고(scraped_notices)를 한 목록으로.

    두 테이블은 id가 겹칠 수 있으므로 (notice_type, id)가 식별자다 — 태그의 다형 참조와 같은 규칙.
    URL 출처의 source_id 자리에는 scraper_id가 들어간다.
    """
    bid = (
        select(
            literal("bid").label("notice_type"), BidNotice.id, BidNotice.source_id,
            SystemSource.name.label("source_name"), BidNotice.bid_no, BidNotice.title,
            BidNotice.organization, BidNotice.start_date, BidNotice.end_date, BidNotice.status,
            BidNotice.url, BidNotice.detail_url, func.coalesce(BidNotice.content, "").label("content"),
            BidNotice.budget, func.coalesce(BidNotice.region, "").label("region"),
            func.coalesce(BidNotice.category, "").label("category"), BidNotice.collected_at,
            BidNotice.attachments, BidNotice.extra,
        )
        .join(SystemSource, SystemSource.id == BidNotice.source_id)
        .where(BidNotice.source_id.in_(system_source_ids))
    )
    scraped = (
        select(
            literal("scraped").label("notice_type"), ScrapedNotice.id,
            ScrapedNotice.scraper_id.label("source_id"),
            func.coalesce(TenantSourceSubscription.custom_name, ScraperRegistry.name).label("source_name"),
            ScrapedNotice.bid_no, ScrapedNotice.title, ScrapedNotice.organization,
            ScrapedNotice.start_date, ScrapedNotice.end_date,
            func.coalesce(ScrapedNotice.status, "ongoing").label("status"),
            ScrapedNotice.url, ScrapedNotice.detail_url,
            func.coalesce(ScrapedNotice.content, "").label("content"), ScrapedNotice.budget,
            func.coalesce(ScrapedNotice.region, "").label("region"),
            cast(literal(""), String).label("category"), ScrapedNotice.collected_at,
            ScrapedNotice.attachments, ScrapedNotice.extra,
        )
        .join(ScraperRegistry, ScraperRegistry.id == ScrapedNotice.scraper_id)
        .join(TenantSourceSubscription, and_(
            TenantSourceSubscription.scraper_id == ScrapedNotice.scraper_id,
            TenantSourceSubscription.tenant_id == tenant_id,
            TenantSourceSubscription.is_active.is_(True),
        ))
    )
    return union_all(bid, scraped).subquery("n")


def _match_keywords(title: str, content: str, keywords: list[str]) -> list[str]:
    """공고 제목+내용에서 매칭되는 키워드 목록 반환."""
    text = (title + " " + content).lower()
    return [kw for kw in keywords if kw.lower() in text]


@router.get("", response_model=NoticeListResponse)
async def list_notices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    source_id: int | None = None,
    scraper_id: int | None = None,
    status: str | None = None,
    tag: str | None = None,
    region: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공고 목록 조회.

    기본 동작:
    1. 사용자가 구독한 출처의 공고만 표시 — 공공 API 출처 + 직접 추가한 URL 출처(2026-09-23)
    2. 키워드가 있으면 자동으로 키워드 매칭 적용
    3. 정렬: 등록일 내림차순 + 매칭 키워드 수 내림차순
    source_id는 공공 출처, scraper_id는 URL 출처로만 좁힌다.
    """
    sub_result = await db.execute(
        select(TenantSystemSubscription.system_source_id).where(
            TenantSystemSubscription.tenant_id == user.tenant_id
        )
    )
    subscribed_ids = [row[0] for row in sub_result.all()]

    kw_result = await db.execute(
        select(TenantKeyword.keyword).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.is_active.is_(True),
        )
    )
    keywords = [row[0] for row in kw_result.all()]

    n = _merged_notices_subquery(user.tenant_id, subscribed_ids)
    conds = []

    if source_id:
        conds += [n.c.notice_type == "bid", n.c.source_id == source_id]
    if scraper_id:
        conds += [n.c.notice_type == "scraped", n.c.source_id == scraper_id]
    if status:
        conds.append(n.c.status == status)
    if q:
        conds.append(or_(
            n.c.title.ilike(f"%{q}%"), n.c.organization.ilike(f"%{q}%"), n.c.content.ilike(f"%{q}%"),
        ))
    elif keywords:  # 키워드 매칭 (별도 검색어가 없을 때)
        conds.append(or_(*[
            or_(n.c.title.ilike(f"%{kw}%"), n.c.content.ilike(f"%{kw}%")) for kw in keywords
        ]))
    if tag:
        tagged = select(TenantTag.notice_type, TenantTag.notice_id).where(
            TenantTag.tenant_id == user.tenant_id, TenantTag.tag == tag,
        )
        conds.append(tuple_(n.c.notice_type, n.c.id).in_(tagged))
    if region:
        region_list = [r.strip() for r in region.split(",") if r.strip()]
        if region_list:
            conds.append(or_(*[n.c.region.ilike(f"%{r}%") for r in region_list]))

    total = await db.scalar(select(func.count()).select_from(n).where(*conds)) or 0

    # 정렬: 등록일 내림차순 (키워드 수 정렬은 Python에서). 같은 날짜는 수집 시각·id로 고정 — 페이지 경계가 흔들리지 않게
    rows = (await db.execute(
        select(n).where(*conds)
        .order_by(n.c.start_date.desc().nulls_last(), n.c.collected_at.desc().nulls_last(), n.c.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).mappings().all()

    tag_map = {
        (t, i): v
        for t in ("bid", "scraped")
        for i, v in (await _build_tag_map(
            db, user.tenant_id, t, [r["id"] for r in rows if r["notice_type"] == t]
        )).items()
    }

    items = [
        BidNoticeResponse(
            **r,
            matched_keywords=_match_keywords(r["title"], r["content"], keywords) if keywords else [],
            tag=tag_map.get((r["notice_type"], r["id"])),
        )
        for r in rows
    ]

    # 키워드 수 내림차순 재정렬 (같은 등록일 내에서)
    items.sort(key=lambda x: len(x.matched_keywords), reverse=True)

    return NoticeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/pre-specs", response_model=NoticeListResponse)
async def list_pre_spec_notices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    region: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사전규격(입찰 예고) 공고 목록. 나라장터 사전규격 source 고정, 키워드 필터링 적용."""
    # 사전규격 소스 조회
    src_result = await db.execute(
        select(SystemSource).where(SystemSource.collector_type == "nara_prespec")
    )
    prespec_source = src_result.scalar_one_or_none()
    if not prespec_source:
        return NoticeListResponse(items=[], total=0, page=page, page_size=page_size)

    source_id = prespec_source.id
    source_name = prespec_source.name

    # 키워드 조회
    kw_result = await db.execute(
        select(TenantKeyword.keyword).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.is_active.is_(True),
        )
    )
    keywords = [row[0] for row in kw_result.all()]

    # 쿼리 구성
    query = select(BidNotice).where(BidNotice.source_id == source_id)
    count_query = select(func.count()).select_from(BidNotice).where(
        BidNotice.source_id == source_id
    )

    if status:
        query = query.where(BidNotice.status == status)
        count_query = count_query.where(BidNotice.status == status)

    if q:
        search_filter = or_(
            BidNotice.title.ilike(f"%{q}%"),
            BidNotice.organization.ilike(f"%{q}%"),
            BidNotice.content.ilike(f"%{q}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    elif keywords:
        kw_filters = [
            or_(
                BidNotice.title.ilike(f"%{kw}%"),
                BidNotice.content.ilike(f"%{kw}%"),
            )
            for kw in keywords
        ]
        combined = or_(*kw_filters)
        query = query.where(combined)
        count_query = count_query.where(combined)

    # 태그 필터
    if tag:
        tagged_ids_q = select(TenantTag.notice_id).where(
            TenantTag.tenant_id == user.tenant_id,
            TenantTag.notice_type == "bid",
            TenantTag.tag == tag,
        )
        query = query.where(BidNotice.id.in_(tagged_ids_q))
        count_query = count_query.where(BidNotice.id.in_(tagged_ids_q))

    # 지역 필터 (콤마 구분 다중 값)
    if region:
        region_list = [r.strip() for r in region.split(",") if r.strip()]
        if region_list:
            region_filters = [BidNotice.region.ilike(f"%{r}%") for r in region_list]
            region_cond = or_(*region_filters)
            query = query.where(region_cond)
            count_query = count_query.where(region_cond)

    total = await db.scalar(count_query) or 0

    query = (
        query.order_by(BidNotice.start_date.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    notices = result.scalars().all()

    notice_ids = [n.id for n in notices]
    tag_map = await _build_tag_map(db, user.tenant_id, "bid", notice_ids)

    items = []
    for n in notices:
        matched = _match_keywords(n.title, n.content or "", keywords) if keywords else []
        items.append(BidNoticeResponse(
            id=n.id,
            source_id=n.source_id,
            source_name=source_name,
            bid_no=n.bid_no,
            title=n.title,
            organization=n.organization,
            start_date=n.start_date,
            end_date=n.end_date,
            status=n.status,
            url=n.url,
            detail_url=n.detail_url,
            content=n.content or "",
            budget=n.budget,
            region=n.region or "",
            category=n.category or "",
            collected_at=n.collected_at,
            matched_keywords=matched,
            tag=tag_map.get(n.id),
            attachments=n.attachments,
            extra=n.extra,
        ))

    items.sort(key=lambda x: len(x.matched_keywords), reverse=True)

    return NoticeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/scraped/{notice_id}", response_model=BidNoticeResponse)
async def get_scraped_notice(
    notice_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """직접 추가한 URL 출처 공고 상세. 그 사이트를 구독 중인 회사만 볼 수 있다
    — 다른 회사가 어떤 사이트를 지켜보는지가 드러나지 않게(공고 자체는 공유 데이터여도)."""
    n = _merged_notices_subquery(user.tenant_id, [])
    row = (await db.execute(
        select(n).where(n.c.notice_type == "scraped", n.c.id == notice_id)
    )).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    kw_result = await db.execute(
        select(TenantKeyword.keyword).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.is_active.is_(True),
        )
    )
    keywords = [r[0] for r in kw_result.all()]
    tag_map = await _build_tag_map(db, user.tenant_id, "scraped", [notice_id])
    return BidNoticeResponse(
        **row,
        matched_keywords=_match_keywords(row["title"], row["content"], keywords) if keywords else [],
        tag=tag_map.get(notice_id),
    )


@router.get("/{notice_id}", response_model=BidNoticeResponse)
async def get_notice(
    notice_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notice = await db.get(BidNotice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    # 상세 보충: content가 비어있으면 bid-collectors fetch_detail 호출
    source = await db.get(SystemSource, notice.source_id)
    if source:
        from app.services.notice import enrich_notice_detail
        await enrich_notice_detail(notice, source, db)

    # source_name
    source_name = source.name if source else ""

    # 키워드 매칭
    kw_result = await db.execute(
        select(TenantKeyword.keyword).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.is_active.is_(True),
        )
    )
    keywords = [row[0] for row in kw_result.all()]
    matched = _match_keywords(notice.title, notice.content or "", keywords) if keywords else []

    # 태그 조회
    tag_result = await db.execute(
        select(TenantTag.tag).where(
            TenantTag.tenant_id == user.tenant_id,
            TenantTag.notice_type == "bid",
            TenantTag.notice_id == notice.id,
        )
    )
    notice_tag = tag_result.scalar_one_or_none()

    return BidNoticeResponse(
        id=notice.id,
        source_id=notice.source_id,
        source_name=source_name,
        bid_no=notice.bid_no,
        title=notice.title,
        organization=notice.organization,
        start_date=notice.start_date,
        end_date=notice.end_date,
        status=notice.status,
        url=notice.url,
        detail_url=notice.detail_url,
        content=notice.content or "",
        budget=notice.budget,
        region=notice.region or "",
        category=notice.category or "",
        collected_at=notice.collected_at,
        matched_keywords=matched,
        tag=notice_tag,
        attachments=notice.attachments,
        extra=notice.extra,
    )


