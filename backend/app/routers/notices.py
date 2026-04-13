from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.keyword import TenantKeyword
from app.models.notice import BidNotice, SystemSource
from app.models.subscription import TenantSystemSubscription
from app.models.tenant import User
from app.schemas.notice import BidNoticeResponse, NoticeListResponse

router = APIRouter(prefix="/api/notices", tags=["notices"])


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
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공고 목록 조회.

    기본 동작:
    1. 사용자가 구독한 출처의 공고만 표시
    2. 키워드가 있으면 자동으로 키워드 매칭 적용
    3. 정렬: 등록일 내림차순 + 매칭 키워드 수 내림차순
    """
    # 1. 구독 출처 조회
    sub_result = await db.execute(
        select(TenantSystemSubscription.system_source_id).where(
            TenantSystemSubscription.tenant_id == user.tenant_id
        )
    )
    subscribed_ids = [row[0] for row in sub_result.all()]

    if not subscribed_ids:
        return NoticeListResponse(items=[], total=0, page=page, page_size=page_size)

    # 2. 출처명 매핑
    src_result = await db.execute(
        select(SystemSource.id, SystemSource.name).where(
            SystemSource.id.in_(subscribed_ids)
        )
    )
    source_names = {row[0]: row[1] for row in src_result.all()}

    # 3. 키워드 조회
    kw_result = await db.execute(
        select(TenantKeyword.keyword).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.is_active.is_(True),
        )
    )
    keywords = [row[0] for row in kw_result.all()]

    # 4. 쿼리 구성
    query = select(BidNotice)
    count_query = select(func.count()).select_from(BidNotice)

    # 구독 출처 필터
    if source_id:
        if source_id not in subscribed_ids:
            return NoticeListResponse(items=[], total=0, page=page, page_size=page_size)
        query = query.where(BidNotice.source_id == source_id)
        count_query = count_query.where(BidNotice.source_id == source_id)
    else:
        query = query.where(BidNotice.source_id.in_(subscribed_ids))
        count_query = count_query.where(BidNotice.source_id.in_(subscribed_ids))

    # 상태 필터
    if status:
        query = query.where(BidNotice.status == status)
        count_query = count_query.where(BidNotice.status == status)

    # 자유 검색
    if q:
        search_filter = or_(
            BidNotice.title.ilike(f"%{q}%"),
            BidNotice.organization.ilike(f"%{q}%"),
            BidNotice.content.ilike(f"%{q}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # 키워드 매칭 (키워드가 있고 별도 검색어가 없을 때)
    if keywords and not q:
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

    # 총 건수
    total = await db.scalar(count_query) or 0

    # 정렬: 등록일 내림차순 (키워드 수 정렬은 Python에서 처리)
    query = (
        query.order_by(BidNotice.start_date.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    notices = result.scalars().all()

    # 5. 응답 구성: 출처명 + 매칭 키워드 추가
    items = []
    for n in notices:
        matched = _match_keywords(n.title, n.content or "", keywords) if keywords else []
        items.append(BidNoticeResponse(
            id=n.id,
            source_id=n.source_id,
            source_name=source_names.get(n.source_id, ""),
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
            attachments=n.attachments,
            extra=n.extra,
        ))

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

    total = await db.scalar(count_query) or 0

    query = (
        query.order_by(BidNotice.start_date.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    notices = result.scalars().all()

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
    # 나라장터는 목록 API에서 가져온 데이터가 전부 (상세 API 없음, 스크래핑 불가)
    source = await db.get(SystemSource, notice.source_id)
    SKIP_DETAIL_TYPES = {"nara"}
    if source and not notice.content and source.collector_type not in SKIP_DETAIL_TYPES:
        detail = await _fetch_detail_via_collector(source.collector_type, notice.bid_no)
        if detail:
            if detail.get("content"):
                notice.content = detail["content"]
            # extra 병합
            extra = dict(notice.extra or {})
            for key, val in detail.items():
                if key not in ("content", "attachments") and val and not extra.get(key):
                    extra[key] = val
            notice.extra = extra
            # 추가 첨부파일 병합
            if detail.get("attachments"):
                existing = notice.attachments or []
                existing_urls = {a["url"] for a in existing}
                for att in detail["attachments"]:
                    if att["url"] not in existing_urls:
                        existing.append(att)
                notice.attachments = existing
            if detail.get("apply_url") and not notice.detail_url:
                notice.detail_url = detail["apply_url"]
            await db.commit()

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
        attachments=notice.attachments,
        extra=notice.extra,
    )


async def _fetch_detail_via_collector(collector_type: str, bid_no: str) -> dict | None:
    """bid-collectors 패키지의 fetch_detail을 호출."""
    from app.tasks.collect_api import _get_collector

    try:
        collector = _get_collector(collector_type)
        return await collector.fetch_detail(bid_no)
    except Exception:
        return None
