"""Favorites orchestration service."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.repositories.favorite_repo import FavoriteRepository
from app.stores.interfaces import ContentStore

LOGGER = logging.getLogger(__name__)


def _mask_user_id(user_id: str) -> str:
    return mask_sensitive(user_id, left=2, right=2)


class FavoriteService:
    @staticmethod
    def add_favorite(
        db: Session,
        user_id: str,
        conclusion_id: str,
        content_store: ContentStore,
    ) -> None:
        LOGGER.info(
            "favorites add start | request_id=%s user_id=%s conclusion_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
            conclusion_id,
        )

        if not content_store.exists(conclusion_id):
            LOGGER.warning(
                "favorites add rejected | request_id=%s user_id=%s conclusion_id=%s reason=conclusion_not_found",
                get_request_id(),
                _mask_user_id(user_id),
                conclusion_id,
            )
            raise BizException(code=4040, message="结论不存在")

        if FavoriteRepository.exists(db, user_id, conclusion_id):
            LOGGER.debug(
                "favorites add skipped | request_id=%s user_id=%s conclusion_id=%s reason=already_exists",
                get_request_id(),
                _mask_user_id(user_id),
                conclusion_id,
            )
            return

        FavoriteRepository.create(db, user_id, conclusion_id)
        LOGGER.info(
            "favorites add success | request_id=%s user_id=%s conclusion_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
            conclusion_id,
        )

    @staticmethod
    def remove_favorite(db: Session, user_id: str, conclusion_id: str) -> None:
        LOGGER.info(
            "favorites remove start | request_id=%s user_id=%s conclusion_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
            conclusion_id,
        )
        FavoriteRepository.delete(db, user_id, conclusion_id)
        LOGGER.info(
            "favorites remove complete | request_id=%s user_id=%s conclusion_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
            conclusion_id,
        )

    @staticmethod
    def list_favorites(db: Session, user_id: str, content_store: ContentStore) -> dict:
        LOGGER.debug(
            "favorites list start | request_id=%s user_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
        )
        favorite_ids = FavoriteRepository.list_ids(db, user_id)
        items = []

        for conclusion_id in favorite_ids:
            summary = content_store.get_summary(conclusion_id)
            if not summary:
                LOGGER.warning(
                    "favorites summary missing | request_id=%s user_id=%s conclusion_id=%s",
                    get_request_id(),
                    _mask_user_id(user_id),
                    conclusion_id,
                )
                continue
            items.append(
                {
                    "conclusion_id": summary["id"],
                    "title": summary["title"],
                    "module": summary["module"],
                }
            )

        items.sort(key=lambda x: x["conclusion_id"])

        result = {
            "total": len(items),
            "items": items,
        }
        LOGGER.info(
            "favorites list complete | request_id=%s user_id=%s total=%s",
            get_request_id(),
            _mask_user_id(user_id),
            result["total"],
        )
        return result

    @staticmethod
    def get_favorite_ids(db: Session, user_id: str) -> set[str]:
        favorite_ids = FavoriteRepository.list_ids(db, user_id)
        LOGGER.debug(
            "favorites ids fetched | request_id=%s user_id=%s count=%s",
            get_request_id(),
            _mask_user_id(user_id),
            len(favorite_ids),
        )
        return favorite_ids
