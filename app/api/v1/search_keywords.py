from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.services.search_keyword_service import SearchKeywordService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/admin/search-keywords")
def list_search_keywords(
    keyword: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "search keywords admin list api received | request_id=%s "
            "user_id=%s keyword=%r page=%s page_size=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        summarize_text(keyword or "", max_length=80),
        page,
        page_size,
    )
    data = SearchKeywordService.list_keywords(
        db=db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    LOGGER.info(
        (
            "search keywords admin list api success | request_id=%s "
            "user_id=%s total=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)
