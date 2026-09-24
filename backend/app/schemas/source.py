from datetime import datetime

from pydantic import BaseModel, field_validator


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


class BuiltinSiteResponse(BaseModel):
    """기본 제공 사이트 — 운영자가 미리 등록한 것만(사용자가 추가한 URL은 다른 회사에 보이지 않는다)."""
    id: int
    name: str
    url: str
    status: str
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

    @field_validator("custom_name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        # 빈 이름이 저장되면 목록·출처 선택에 이름 없는 출처가 생긴다
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("이름을 입력하세요")
        if len(v) > 100:
            raise ValueError("이름은 100자 이내로 입력하세요")
        return v
