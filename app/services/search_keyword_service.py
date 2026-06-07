from __future__ import annotations

import csv
import io
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.logging_helpers import summarize_text
from app.core.request_context import get_request_id
from app.models.search_keyword import SearchKeyword
from app.repositories.search_keyword_repo import SearchKeywordRepository

LOGGER = logging.getLogger(__name__)
MAX_KEYWORD_LENGTH = 255


def _normalize_keyword(keyword: str) -> str:
    return " ".join(str(keyword or "").strip().split())[:MAX_KEYWORD_LENGTH]


def _normalize_keyword_key(keyword: str) -> str:
    return _normalize_keyword(keyword).lower()


def _normalize_result_count(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _to_item(row: SearchKeyword) -> dict:
    return {
        "id": row.id,
        "keyword": row.keyword,
        "normalized_keyword": row.normalized_keyword,
        "search_count": row.search_count,
        "no_result_count": row.no_result_count,
        "last_result_count": row.last_result_count,
        "last_has_result": row.last_has_result,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _format_bool(value: bool) -> str:
    return "是" if value else "否"


class SearchKeywordService:
    @staticmethod
    def record_keyword(db: Session, keyword: str, result_count: int = 0) -> None:
        normalized_keyword = _normalize_keyword(keyword)
        normalized_key = _normalize_keyword_key(keyword)
        if not normalized_keyword or not normalized_key:
            return

        safe_result_count = _normalize_result_count(result_count)
        LOGGER.debug(
            "search keyword record start | request_id=%s keyword=%r result_count=%s",
            get_request_id(),
            summarize_text(normalized_keyword, max_length=80),
            safe_result_count,
        )
        SearchKeywordRepository.record_keyword(
            db,
            keyword=normalized_keyword,
            normalized_keyword=normalized_key,
            result_count=safe_result_count,
        )

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
    ) -> dict:
        rows, total = SearchKeywordRepository.list_keywords(
            db,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            result_filter=result_filter,
            low_result_threshold=low_result_threshold,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )
        no_result_total, low_result_total = SearchKeywordRepository.count_result_buckets(
            db,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            low_result_threshold=low_result_threshold,
        )
        return {
            "total": total,
            "no_result_total": no_result_total,
            "low_result_total": low_result_total,
            "page": page,
            "page_size": page_size,
            "items": [_to_item(row) for row in rows],
        }

    @staticmethod
    def export_keywords_csv(
        db: Session,
        *,
        keyword: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        result_filter: str = "all",
        low_result_threshold: int = 3,
        sort_by: str = "search_count",
    ) -> str:
        rows = SearchKeywordRepository.list_keywords_for_export(
            db,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            result_filter=result_filter,
            low_result_threshold=low_result_threshold,
            sort_by=sort_by,
        )
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow([
            "ID",
            "搜索词",
            "归一化搜索词",
            "搜索次数",
            "无结果次数",
            "最近结果数",
            "最近是否有结果",
            "首次搜索时间",
            "最近搜索时间",
        ])
        for row in rows:
            writer.writerow([
                row.id,
                row.keyword,
                row.normalized_keyword,
                row.search_count,
                row.no_result_count,
                row.last_result_count,
                _format_bool(bool(row.last_has_result)),
                row.created_at.isoformat(),
                row.updated_at.isoformat(),
            ])
        return output.getvalue()
