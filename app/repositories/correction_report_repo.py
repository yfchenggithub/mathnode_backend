from __future__ import annotations

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.correction_report import CorrectionReport


class CorrectionReportRepository:
    @staticmethod
    def create(db: Session, values: dict[str, object]) -> CorrectionReport:
        obj = CorrectionReport(**values)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def list_reports(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CorrectionReport], int]:
        conditions = []

        if status:
            conditions.append(CorrectionReport.status == status)

        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    CorrectionReport.conclusion_id.like(keyword_pattern),
                    CorrectionReport.conclusion_title.like(keyword_pattern),
                    CorrectionReport.description.like(keyword_pattern),
                )
            )

        stmt = select(CorrectionReport)
        count_stmt = select(func.count()).select_from(CorrectionReport)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = int(db.execute(count_stmt).scalar_one() or 0)
        offset = max(0, page - 1) * page_size
        rows = (
            db.execute(
                stmt.order_by(
                    desc(CorrectionReport.created_at),
                    desc(CorrectionReport.id),
                )
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total
