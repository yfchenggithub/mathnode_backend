from __future__ import annotations

import logging

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
        "last_result_count": row.last_result_count,
        "last_has_result": row.last_has_result,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


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
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        rows, total = SearchKeywordRepository.list_keywords(
            db,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_to_item(row) for row in rows],
        }
