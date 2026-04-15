from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.repositories.recent_search_repo import RecentSearchRepository

LOGGER = logging.getLogger(__name__)


def _mask_user_id(user_id: str) -> str:
    return mask_sensitive(user_id, left=2, right=2)


class RecentSearchService:
    @staticmethod
    def add_keyword(db: Session, user_id: str, keyword: str) -> None:
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            return

        LOGGER.debug(
            "recent search add | request_id=%s user_id=%s keyword=%r",
            get_request_id(),
            _mask_user_id(user_id),
            summarize_text(normalized_keyword, max_length=80),
        )
        RecentSearchRepository.add_keyword(db, user_id, normalized_keyword, keep_limit=10)

    @staticmethod
    def list_recent(db: Session, user_id: str, limit: int = 10) -> dict:
        LOGGER.debug(
            "recent search list start | request_id=%s user_id=%s limit=%s",
            get_request_id(),
            _mask_user_id(user_id),
            limit,
        )
        rows = RecentSearchRepository.list_recent(db, user_id, limit=limit)
        result = {
            "total": len(rows),
            "items": [
                {
                    "keyword": row.keyword,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
        }
        LOGGER.info(
            "recent search list complete | request_id=%s user_id=%s total=%s",
            get_request_id(),
            _mask_user_id(user_id),
            result["total"],
        )
        return result

    @staticmethod
    def clear_all(db: Session, user_id: str) -> None:
        LOGGER.info(
            "recent search clear | request_id=%s user_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
        )
        RecentSearchRepository.clear_all(db, user_id)
