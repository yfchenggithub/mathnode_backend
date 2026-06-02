from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.search_keyword import SearchKeyword


class SearchKeywordRepository:
    @staticmethod
    def record_keyword(
        db: Session,
        *,
        keyword: str,
        normalized_keyword: str,
        result_count: int,
    ) -> SearchKeyword:
        now = datetime.now(UTC).replace(tzinfo=None)
        row = SearchKeywordRepository.get_by_normalized_keyword(
            db,
            normalized_keyword=normalized_keyword,
        )
        if row is not None:
            return SearchKeywordRepository._update_keyword(
                db,
                row=row,
                keyword=keyword,
                result_count=result_count,
                updated_at=now,
            )

        row = SearchKeyword(
            keyword=keyword,
            normalized_keyword=normalized_keyword,
            search_count=1,
            last_result_count=result_count,
            last_has_result=result_count > 0,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
            row = SearchKeywordRepository.get_by_normalized_keyword(
                db,
                normalized_keyword=normalized_keyword,
            )
            if row is None:
                raise
            return SearchKeywordRepository._update_keyword(
                db,
                row=row,
                keyword=keyword,
                result_count=result_count,
                updated_at=now,
            )

    @staticmethod
    def get_by_normalized_keyword(
        db: Session,
        *,
        normalized_keyword: str,
    ) -> SearchKeyword | None:
        stmt = select(SearchKeyword).where(
            SearchKeyword.normalized_keyword == normalized_keyword
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_keywords(
        db: Session,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SearchKeyword], int]:
        conditions = []
        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    SearchKeyword.keyword.like(keyword_pattern),
                    SearchKeyword.normalized_keyword.like(keyword_pattern),
                )
            )

        stmt = select(SearchKeyword)
        count_stmt = select(func.count()).select_from(SearchKeyword)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = int(db.execute(count_stmt).scalar_one() or 0)
        offset = max(0, page - 1) * page_size
        rows = (
            db.execute(
                stmt.order_by(
                    desc(SearchKeyword.updated_at),
                    desc(SearchKeyword.id),
                )
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    def _update_keyword(
        db: Session,
        *,
        row: SearchKeyword,
        keyword: str,
        result_count: int,
        updated_at: datetime,
    ) -> SearchKeyword:
        row.keyword = keyword
        row.search_count = int(row.search_count or 0) + 1
        row.last_result_count = result_count
        row.last_has_result = result_count > 0
        row.updated_at = updated_at
        db.commit()
        db.refresh(row)
        return row
