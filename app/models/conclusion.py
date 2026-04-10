from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conclusion(Base):
    __tablename__ = "conclusions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    module: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    difficulty: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False, default=1
    )

    # 最小可运行：标签先用逗号分隔字符串存储
    tags: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # 搜索页轻展示
    statement_clean: Mapped[str] = mapped_column(Text, nullable=False)

    # 详情页
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    proof: Mapped[str] = mapped_column(Text, nullable=False)
    examples_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    traps_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
