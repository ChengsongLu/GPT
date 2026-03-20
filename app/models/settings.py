from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    gitlab_base_url: Mapped[str | None] = mapped_column(String(500))
    gitlab_token: Mapped[str | None] = mapped_column(String(500))
    gitlab_project_ref: Mapped[str | None] = mapped_column(String(500))
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Shanghai", nullable=False)
    feishu_app_id: Mapped[str | None] = mapped_column(String(255))
    feishu_app_secret: Mapped[str | None] = mapped_column(String(255))
    feishu_bitable_app_token: Mapped[str | None] = mapped_column(String(255))
    feishu_bitable_table_id: Mapped[str | None] = mapped_column(String(255))
    feishu_chat_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
