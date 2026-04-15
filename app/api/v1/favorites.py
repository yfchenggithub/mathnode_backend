from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store
from app.api.deps import get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.favorite import FavoriteCreateRequest
from app.services.favorite_service import FavoriteService
from app.stores.interfaces import ContentStore

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/favorites")
def add_favorite(
    payload: FavoriteCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
):
    LOGGER.info(
        "favorites add api received | request_id=%s user_id=%s conclusion_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        payload.conclusion_id,
    )
    FavoriteService.add_favorite(
        db=db,
        user_id=user_id,
        conclusion_id=payload.conclusion_id,
        content_store=content_store,
    )
    LOGGER.info(
        "favorites add api success | request_id=%s user_id=%s conclusion_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        payload.conclusion_id,
    )
    return success_response(message="收藏成功")


@router.delete("/favorites/{conclusion_id}")
def remove_favorite(
    conclusion_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "favorites remove api received | request_id=%s user_id=%s conclusion_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        conclusion_id,
    )
    FavoriteService.remove_favorite(db=db, user_id=user_id, conclusion_id=conclusion_id)
    LOGGER.info(
        "favorites remove api success | request_id=%s user_id=%s conclusion_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        conclusion_id,
    )
    return success_response(message="取消收藏成功")


@router.get("/favorites")
def list_favorites(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
):
    LOGGER.info(
        "favorites list api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    data = FavoriteService.list_favorites(
        db=db,
        user_id=user_id,
        content_store=content_store,
    )
    LOGGER.info(
        "favorites list api success | request_id=%s user_id=%s total=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)
