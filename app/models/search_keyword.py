from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchKeyword(Base):
    __tablename__ = "search_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    keyword: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    search_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_has_result: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
