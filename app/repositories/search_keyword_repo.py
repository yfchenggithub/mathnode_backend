from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, desc, func, or_, select
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
        now = datetime.now(timezone.utc).replace(tzinfo=None)
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
            no_result_count=1 if result_count <= 0 else 0,
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
        start_date: date | None = None,
        end_date: date | None = None,
        result_filter: str = "all",
        low_result_threshold: int = 3,
        sort_by: str = "search_count",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SearchKeyword], int]:
        conditions = SearchKeywordRepository._build_filter_conditions(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            result_filter=result_filter,
            low_result_threshold=low_result_threshold,
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
                SearchKeywordRepository._apply_order(stmt, sort_by)
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    def list_keywords_for_export(
        db: Session,
        *,
        keyword: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        result_filter: str = "all",
        low_result_threshold: int = 3,
        sort_by: str = "search_count",
    ) -> list[SearchKeyword]:
        conditions = SearchKeywordRepository._build_filter_conditions(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            result_filter=result_filter,
            low_result_threshold=low_result_threshold,
        )
        stmt = select(SearchKeyword)
        if conditions:
            stmt = stmt.where(*conditions)

        rows = db.execute(SearchKeywordRepository._apply_order(stmt, sort_by)).scalars().all()
        return list(rows)

    @staticmethod
    def count_result_buckets(
        db: Session,
        *,
        keyword: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        low_result_threshold: int = 3,
    ) -> tuple[int, int]:
        base_conditions = SearchKeywordRepository._build_filter_conditions(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            result_filter="all",
            low_result_threshold=low_result_threshold,
        )
        safe_threshold = max(1, int(low_result_threshold or 1))
        no_result_conditions = [
            *base_conditions,
            SearchKeywordRepository._no_result_condition(),
        ]
        low_result_conditions = [
            *base_conditions,
            and_(
                SearchKeyword.last_result_count > 0,
                SearchKeyword.last_result_count <= safe_threshold,
            ),
        ]

        no_result_stmt = select(func.count()).select_from(SearchKeyword).where(
            *no_result_conditions
        )
        low_result_stmt = select(func.count()).select_from(SearchKeyword).where(
            *low_result_conditions
        )
        no_result_total = int(db.execute(no_result_stmt).scalar_one() or 0)
        low_result_total = int(db.execute(low_result_stmt).scalar_one() or 0)
        return no_result_total, low_result_total

    @staticmethod
    def _build_filter_conditions(
        *,
        keyword: str | None,
        start_date: date | None,
        end_date: date | None,
        result_filter: str,
        low_result_threshold: int,
    ) -> list:
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

        if start_date is not None:
            conditions.append(
                SearchKeyword.updated_at >= datetime.combine(start_date, time.min)
            )
        if end_date is not None:
            end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)
            conditions.append(SearchKeyword.updated_at < end_exclusive)

        if result_filter == "no_result":
            conditions.append(SearchKeywordRepository._no_result_condition())
        elif result_filter == "low_result":
            safe_threshold = max(1, int(low_result_threshold or 1))
            conditions.append(
                and_(
                    SearchKeyword.last_result_count > 0,
                    SearchKeyword.last_result_count <= safe_threshold,
                )
            )

        return conditions

    @staticmethod
    def _no_result_condition():
        return or_(
            SearchKeyword.no_result_count > 0,
            SearchKeyword.last_has_result.is_(False),
            SearchKeyword.last_result_count <= 0,
        )

    @staticmethod
    def _apply_order(stmt, sort_by: str):
        if sort_by == "recent":
            return stmt.order_by(
                desc(SearchKeyword.updated_at),
                desc(SearchKeyword.id),
            )

        if sort_by == "no_result_count":
            return stmt.order_by(
                desc(SearchKeyword.no_result_count),
                desc(SearchKeyword.search_count),
                desc(SearchKeyword.updated_at),
                desc(SearchKeyword.id),
            )

        return stmt.order_by(
            desc(SearchKeyword.search_count),
            desc(SearchKeyword.updated_at),
            desc(SearchKeyword.id),
        )

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
        if result_count <= 0:
            row.no_result_count = int(row.no_result_count or 0) + 1
        row.last_result_count = result_count
        row.last_has_result = result_count > 0
        row.updated_at = updated_at
        db.commit()
        db.refresh(row)
        return row
