from datetime import date, datetime

from pydantic import BaseModel


class BidNoticeResponse(BaseModel):
    id: int
    source_id: int
    source_name: str = ""
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

    model_config = {"from_attributes": True}


class NoticeListResponse(BaseModel):
    items: list[BidNoticeResponse]
    total: int
    page: int
    page_size: int
