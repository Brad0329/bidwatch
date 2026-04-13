from datetime import datetime

from pydantic import BaseModel, field_validator


class KeywordCreateRequest(BaseModel):
    keyword: str
    keyword_group: str | None = None

    @field_validator("keyword")
    @classmethod
    def keyword_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("키워드는 빈 문자열일 수 없습니다")
        return v


class KeywordUpdateRequest(BaseModel):
    is_active: bool | None = None
    keyword_group: str | None = None


class KeywordResponse(BaseModel):
    id: int
    tenant_id: int
    keyword: str
    keyword_group: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
