from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.conclusion import Conclusion


class ConclusionRepository:
    @staticmethod
    def get_by_id(db: Session, conclusion_id: str) -> Conclusion | None:
        stmt = select(Conclusion).where(Conclusion.id == conclusion_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def search(
        db: Session,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Conclusion], int]:
        stmt = select(Conclusion)

        if module:
            stmt = stmt.where(Conclusion.module == module)

        if difficulty is not None:
            stmt = stmt.where(Conclusion.difficulty == difficulty)

        if tag:
            stmt = stmt.where(Conclusion.tags.like(f"%{tag}%"))

        keyword = q.strip()
        if keyword:
            like_expr = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Conclusion.title.like(like_expr),
                    Conclusion.module.like(like_expr),
                    Conclusion.statement_clean.like(like_expr),
                    Conclusion.tags.like(like_expr),
                )
            )

        all_rows = list(db.execute(stmt.order_by(Conclusion.id.asc())).scalars().all())
        total = len(all_rows)

        start = (page - 1) * page_size
        end = start + page_size
        paged_rows = all_rows[start:end]

        return paged_rows, total

    @staticmethod
    def list_all_for_facets(
        db: Session,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
    ) -> list[Conclusion]:
        stmt = select(Conclusion)

        if module:
            stmt = stmt.where(Conclusion.module == module)

        if difficulty is not None:
            stmt = stmt.where(Conclusion.difficulty == difficulty)

        if tag:
            stmt = stmt.where(Conclusion.tags.like(f"%{tag}%"))

        keyword = q.strip()
        if keyword:
            like_expr = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Conclusion.title.like(like_expr),
                    Conclusion.module.like(like_expr),
                    Conclusion.statement_clean.like(like_expr),
                    Conclusion.tags.like(like_expr),
                )
            )

        return list(db.execute(stmt).scalars().all())
