from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.services.recent_search_service import RecentSearchService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/recent-searches")
def list_recent_searches(
    limit: int = Query(default=10, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "recent searches list api received | request_id=%s user_id=%s limit=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        limit,
    )
    data = RecentSearchService.list_recent(db=db, user_id=user_id, limit=limit)
    LOGGER.info(
        "recent searches list api success | request_id=%s user_id=%s total=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)


@router.delete("/recent-searches")
def clear_recent_searches(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "recent searches clear api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    RecentSearchService.clear_all(db=db, user_id=user_id)
    LOGGER.info(
        "recent searches clear api success | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    return success_response(message="最近搜索已清空")
