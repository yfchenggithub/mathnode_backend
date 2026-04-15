"""Search orchestration service."""

from __future__ import annotations

import logging
import time

from app.core.logging_helpers import summarize_text
from app.core.request_context import get_request_id
from app.stores.interfaces import IndexStore

LOGGER = logging.getLogger(__name__)


class SearchService:
    @staticmethod
    def search(
        index_store: IndexStore,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        started_at = time.perf_counter()
        favorite_ids = favorite_ids or set()
        normalized_q = q.strip()

        LOGGER.debug(
            (
                "search start | request_id=%s q_raw=%r q=%r module=%s difficulty=%s "
                "tag=%s page=%s page_size=%s favorite_count=%s index_count=%s"
            ),
            get_request_id(),
            summarize_text(q, max_length=80),
            summarize_text(normalized_q, max_length=80),
            module,
            difficulty,
            summarize_text(tag or "", max_length=60),
            page,
            page_size,
            len(favorite_ids),
            index_store.count(),
        )

        try:
            result = index_store.search(
                q=q,
                module=module,
                difficulty=difficulty,
                tag=tag,
                page=page,
                page_size=page_size,
                favorite_ids=favorite_ids,
            )
        except Exception:
            LOGGER.exception(
                (
                    "search failed | request_id=%s q=%r module=%s difficulty=%s "
                    "tag=%s page=%s page_size=%s"
                ),
                get_request_id(),
                summarize_text(normalized_q, max_length=80),
                module,
                difficulty,
                summarize_text(tag or "", max_length=60),
                page,
                page_size,
            )
            raise

        total = int(result.get("total", 0))
        items = result.get("items", [])
        item_count = len(items) if isinstance(items, list) else 0

        LOGGER.info(
            "search finished | request_id=%s q=%r total=%s returned=%s elapsed_ms=%.2f",
            get_request_id(),
            summarize_text(normalized_q, max_length=80),
            total,
            item_count,
            (time.perf_counter() - started_at) * 1000,
        )
        return result

    @staticmethod
    def suggest(index_store: IndexStore, q: str) -> dict:
        started_at = time.perf_counter()
        normalized_q = q.strip()

        LOGGER.debug(
            "suggest start | request_id=%s q_raw=%r q=%r index_count=%s",
            get_request_id(),
            summarize_text(q, max_length=80),
            summarize_text(normalized_q, max_length=80),
            index_store.count(),
        )

        try:
            result = index_store.suggest(q=q)
        except Exception:
            LOGGER.exception(
                "suggest failed | request_id=%s q=%r",
                get_request_id(),
                summarize_text(normalized_q, max_length=80),
            )
            raise

        total = int(result.get("total", 0))
        items = result.get("items", [])
        item_count = len(items) if isinstance(items, list) else 0

        LOGGER.info(
            "suggest finished | request_id=%s q=%r total=%s returned=%s elapsed_ms=%.2f",
            get_request_id(),
            summarize_text(normalized_q, max_length=80),
            total,
            item_count,
            (time.perf_counter() - started_at) * 1000,
        )
        return result
