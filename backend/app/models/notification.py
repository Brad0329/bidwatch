from datetime import time

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    email_enabled: Mapped[bool] = mapped_column(default=True)
    kakao_enabled: Mapped[bool] = mapped_column(default=False)
    kakao_phone: Mapped[str | None] = mapped_column(default=None)
    notify_new_match: Mapped[bool] = mapped_column(default=True)
    notify_new_notices: Mapped[bool] = mapped_column(default=True)
    notify_deadline: Mapped[bool] = mapped_column(default=True)
    quiet_hours_start: Mapped[time | None] = mapped_column(default=None)
    quiet_hours_end: Mapped[time | None] = mapped_column(default=None)
