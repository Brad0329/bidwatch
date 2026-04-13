from datetime import datetime

from pydantic import BaseModel


class SourceAddRequest(BaseModel):
    url: str


class SourceAddResponse(BaseModel):
    scraper_id: int
    subscription_id: int | None = None
    scraper_status: str  # pending, analyzing, ready, failed
    message: str


class SubscriptionResponse(BaseModel):
    id: int
    scraper_id: int
    scraper_name: str
    scraper_status: str
    scraper_url: str
    custom_name: str | None
    is_active: bool
    last_collected_at: datetime | None
    last_collected_count: int | None

    model_config = {"from_attributes": True}


class SystemSourceResponse(BaseModel):
    id: int
    name: str
    collector_type: str
    is_active: bool
    last_collected_at: datetime | None
    last_collected_count: int | None

    model_config = {"from_attributes": True}


class PreviewResponse(BaseModel):
    scraper_name: str
    notices_count: int
    notices: list[dict]


class SubscriptionUpdateRequest(BaseModel):
    custom_name: str | None = None
    is_active: bool | None = None
