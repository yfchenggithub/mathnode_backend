from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeeklyUpdateContentSnapshot(Base):
    __tablename__ = "weekly_update_content_snapshots"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    observed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
