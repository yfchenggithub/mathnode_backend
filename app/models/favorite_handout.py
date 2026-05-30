from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FavoriteHandout(Base):
    __tablename__ = "favorite_handouts"
    __table_args__ = (UniqueConstraint("handout_id", name="uq_favorite_handout_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    handout_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_conclusion_ids_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
