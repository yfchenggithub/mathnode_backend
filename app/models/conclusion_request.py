from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConclusionRequest(Base):
    __tablename__ = "conclusion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    query: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="home")
    page: Mapped[str] = mapped_column(String(64), nullable=False, default="home")
    entry: Mapped[str] = mapped_column(String(64), nullable=False, default="search_hint")
    active_tab: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="pending",
    )
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