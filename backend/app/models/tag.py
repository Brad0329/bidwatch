from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantTag(Base):
    __tablename__ = "tenant_tags"
    __table_args__ = (
        Index("uq_tenant_tag_notice", "tenant_id", "notice_type", "notice_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    notice_type: Mapped[str]  # 'bid' or 'scraped'
    notice_id: Mapped[int] = mapped_column(BigInteger)
    tag: Mapped[str]  # 검토요청, 입찰대상, 제외, 낙찰, 유찰
    tagged_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    memo: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
