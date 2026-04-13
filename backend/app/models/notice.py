from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemSource(Base):
    __tablename__ = "system_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    collector_type: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(default=None)
    last_collected_count: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class BidNotice(Base):
    __tablename__ = "bid_notices"
    __table_args__ = (
        Index("ix_bid_notices_dates", "start_date", "end_date"),
        Index("ix_bid_notices_status", "status"),
        Index("uq_bid_notices_source_bid_no", "source_id", "bid_no", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("system_sources.id"))
    bid_no: Mapped[str]
    title: Mapped[str]
    organization: Mapped[str] = mapped_column(default="")
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(default="ongoing")
    url: Mapped[str] = mapped_column(default="")
    detail_url: Mapped[str] = mapped_column(default="")
    content: Mapped[str] = mapped_column(Text, default="")
    budget: Mapped[int | None] = mapped_column(BigInteger, default=None)
    region: Mapped[str] = mapped_column(default="")
    category: Mapped[str] = mapped_column(default="")
    attachments: Mapped[dict | None] = mapped_column(JSONB, default=None)
    extra: Mapped[dict | None] = mapped_column(JSONB, default=None)
    collected_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(default=None, onupdate=func.now())
