from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeeklyUpdateSubscription(Base):
    __tablename__ = "weekly_update_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "template_id",
            name="uq_weekly_update_subscription_user_template",
        ),
    )

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default=STATUS_INACTIVE,
        nullable=False,
    )
    available_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_accept_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_reject_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_request_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_prompt_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
