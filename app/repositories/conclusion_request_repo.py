from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.conclusion_request import ConclusionRequest


class ConclusionRequestRepository:
    @staticmethod
    def create(db: Session, values: dict[str, object]) -> ConclusionRequest:
        obj = ConclusionRequest(**values)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def get_by_id(db: Session, request_id: int) -> ConclusionRequest | None:
        stmt = select(ConclusionRequest).where(ConclusionRequest.id == request_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_requests(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ConclusionRequest], int]:
        conditions = []

        if status:
            conditions.append(ConclusionRequest.status == status)

        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    ConclusionRequest.query.like(keyword_pattern),
                    ConclusionRequest.note.like(keyword_pattern),
                )
            )

        stmt = select(ConclusionRequest)
        count_stmt = select(func.count()).select_from(ConclusionRequest)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = int(db.execute(count_stmt).scalar_one() or 0)
        offset = max(0, page - 1) * page_size
        rows = (
            db.execute(
                stmt.order_by(
                    desc(ConclusionRequest.created_at),
                    desc(ConclusionRequest.id),
                )
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    def update_status(
        db: Session,
        request_obj: ConclusionRequest,
        status: str,
    ) -> ConclusionRequest:
        request_obj.status = status
        request_obj.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(request_obj)
        return request_obj