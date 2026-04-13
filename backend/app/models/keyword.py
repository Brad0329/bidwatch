from datetime import datetime

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantKeyword(Base):
    __tablename__ = "tenant_keywords"
    __table_args__ = (
        Index("uq_tenant_keyword", "tenant_id", "keyword", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    keyword: Mapped[str]
    keyword_group: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
