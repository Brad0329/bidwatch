from datetime import datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScraperRegistry(Base):
    __tablename__ = "scraper_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True)
    url_hash: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    scraper_config: Mapped[dict | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(default="pending")  # pending/analyzing/ready/failed
    analysis_log: Mapped[str | None] = mapped_column(Text, default=None)
    subscriber_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(default=None)
    last_collected_count: Mapped[int | None] = mapped_column(default=None)
    created_by_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class TenantSourceSubscription(Base):
    __tablename__ = "tenant_source_subscriptions"
    __table_args__ = (
        Index("uq_tenant_scraper", "tenant_id", "scraper_id", unique=True),
        Index("ix_sub_tenant_active", "tenant_id", postgresql_where="is_active"),
        Index("ix_sub_scraper_active", "scraper_id", postgresql_where="is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    scraper_id: Mapped[int] = mapped_column(ForeignKey("scraper_registry.id"))
    custom_name: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    subscribed_at: Mapped[datetime] = mapped_column(default=func.now())


class ScrapedNotice(Base):
    __tablename__ = "scraped_notices"
    __table_args__ = (
        Index("uq_scraped_notice", "scraper_id", "bid_no", unique=True),
        Index("ix_scraped_scraper_date", "scraper_id", "start_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scraper_id: Mapped[int] = mapped_column(ForeignKey("scraper_registry.id"))
    bid_no: Mapped[str]
    title: Mapped[str]
    organization: Mapped[str] = mapped_column(default="")
    start_date: Mapped[datetime | None] = mapped_column(Date, default=None)
    end_date: Mapped[datetime | None] = mapped_column(Date, default=None)
    status: Mapped[str | None] = mapped_column(default=None)
    url: Mapped[str] = mapped_column(default="")
    detail_url: Mapped[str] = mapped_column(default="")
    content: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[int | None] = mapped_column(BigInteger, default=None)
    region: Mapped[str] = mapped_column(default="")
    attachments: Mapped[dict | None] = mapped_column(JSONB, default=None)
    extra: Mapped[dict | None] = mapped_column(JSONB, default=None)
    collected_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(default=None, onupdate=func.now())
