from datetime import datetime

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantSystemSubscription(Base):
    """테넌트의 시스템 출처(공공 API) 구독."""
    __tablename__ = "tenant_system_subscriptions"
    __table_args__ = (
        Index("uq_tenant_system_sub", "tenant_id", "system_source_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    system_source_id: Mapped[int] = mapped_column(ForeignKey("system_sources.id"))
    subscribed_at: Mapped[datetime] = mapped_column(default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    plan: Mapped[str]
    status: Mapped[str] = mapped_column(default="active")  # active/cancelled/expired
    billing_key: Mapped[str | None] = mapped_column(default=None)
    current_period_start: Mapped[datetime | None] = mapped_column(default=None)
    current_period_end: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
