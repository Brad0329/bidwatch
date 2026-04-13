from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.models.base import Base


class TenantProfile(Base):
    __tablename__ = "tenant_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True)
    company_name: Mapped[str | None] = mapped_column(default=None)
    industry: Mapped[str | None] = mapped_column(default=None)
    size: Mapped[str | None] = mapped_column(default=None)
    region: Mapped[str | None] = mapped_column(default=None)
    business_areas: Mapped[list | None] = mapped_column(ARRAY(String), default=None)
    competency_keywords: Mapped[list | None] = mapped_column(ARRAY(String), default=None)
    min_budget: Mapped[int | None] = mapped_column(BigInteger, default=None)
    max_budget: Mapped[int | None] = mapped_column(BigInteger, default=None)
    preferred_org_types: Mapped[list | None] = mapped_column(ARRAY(String), default=None)
    detail_profile: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class TenantMatch(Base):
    __tablename__ = "tenant_matches"
    __table_args__ = (
        {"comment": "AI matching results - premium feature"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    notice_type: Mapped[str]  # 'bid' or 'scraped'
    notice_id: Mapped[int] = mapped_column(BigInteger)
    match_score: Mapped[int]  # 1~5
    match_reason: Mapped[str | None] = mapped_column(Text, default=None)
    matched_at: Mapped[datetime] = mapped_column(default=func.now())
    is_notified: Mapped[bool] = mapped_column(default=False)
