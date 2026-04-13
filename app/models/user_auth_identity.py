from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAuthIdentity(Base):
    __tablename__ = "user_auth_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_provider_provider_user_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # NOTE: keep plaintext for MVP compatibility; use encryption in production.
    session_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
