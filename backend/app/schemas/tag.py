from datetime import datetime

from pydantic import BaseModel, field_validator

VALID_TAGS = {"검토요청", "입찰대상", "제외", "낙찰", "유찰"}


class TagCreateRequest(BaseModel):
    notice_type: str  # "bid" or "scraped"
    notice_id: int
    tag: str
    memo: str | None = None

    @field_validator("tag")
    @classmethod
    def tag_must_be_valid(cls, v: str) -> str:
        if v not in VALID_TAGS:
            raise ValueError(f"유효하지 않은 태그입니다. 가능한 값: {', '.join(VALID_TAGS)}")
        return v

    @field_validator("notice_type")
    @classmethod
    def notice_type_must_be_valid(cls, v: str) -> str:
        if v not in ("bid", "scraped"):
            raise ValueError("notice_type은 'bid' 또는 'scraped'이어야 합니다")
        return v


class TagUpdateRequest(BaseModel):
    tag: str | None = None
    memo: str | None = None

    @field_validator("tag")
    @classmethod
    def tag_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_TAGS:
            raise ValueError(f"유효하지 않은 태그입니다. 가능한 값: {', '.join(VALID_TAGS)}")
        return v


class TagResponse(BaseModel):
    id: int
    tenant_id: int
    notice_type: str
    notice_id: int
    tag: str
    tagged_by: int
    memo: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
