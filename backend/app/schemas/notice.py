from datetime import date, datetime

from pydantic import BaseModel


class RelatedNotice(BaseModel):
    """상세에서 이어지는 공고 (F-018). kind: "prespec"(본 공고 → 사전규격) | "notice"(사전규격 → 본 공고)
    | "nara"(알리오 → 같은 나라장터 공고, 원문 링크의 공고번호로)."""
    id: int
    kind: str
    bid_no: str
    title: str
    status: str


class BidNoticeResponse(BaseModel):
    # "bid"(공공 API 출처) | "scraped"(직접 추가한 URL 출처) — 두 테이블은 id가 겹치므로 (notice_type, id)가 식별자.
    # scraped면 source_id 자리에 scraper_id가 들어간다.
    notice_type: str = "bid"
    id: int
    source_id: int
    source_name: str = ""
    source_category: str = "bid"  # "bid" | "support"(지원사업 — 목록에 "지원" 배지). services/source_category.py
    bid_no: str
    title: str
    organization: str
    start_date: date | None
    end_date: date | None
    status: str
    url: str
    detail_url: str
    content: str
    budget: int | None
    region: str
    category: str
    collected_at: datetime | None
    matched_keywords: list[str] = []
    tag: str | None = None
    attachments: list[dict] | None = None
    extra: dict | None = None
    related: list[RelatedNotice] = []  # 상세 API만 채운다

    model_config = {"from_attributes": True}


class NoticeListResponse(BaseModel):
    items: list[BidNoticeResponse]
    total: int
    page: int
    page_size: int
