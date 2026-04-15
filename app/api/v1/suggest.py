import logging

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_index_store
from app.core.logging_helpers import summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.services.search_service import SearchService
from app.stores.interfaces import IndexStore

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/suggest")
def suggest(
    q: str = Query(default=""),
    index_store: IndexStore = Depends(get_index_store),
):
    normalized_q = q.strip()
    LOGGER.info(
        "suggest api received | request_id=%s q=%r",
        get_request_id(),
        summarize_text(normalized_q, max_length=80),
    )
    data = SearchService.suggest(index_store=index_store, q=q)
    LOGGER.info(
        "suggest api success | request_id=%s q=%r total=%s returned=%s",
        get_request_id(),
        summarize_text(normalized_q, max_length=80),
        data.get("total"),
        len(data.get("items", [])) if isinstance(data.get("items"), list) else 0,
    )
    return success_response(data=data)
