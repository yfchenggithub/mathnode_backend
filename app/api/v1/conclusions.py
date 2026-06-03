import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store, get_index_store, get_pdf_mapping_store
from app.api.deps import get_current_user_id, get_db, get_optional_user_id
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.services.conclusion_service import ConclusionService
from app.services.favorite_service import FavoriteService
from app.services.search_service import SearchService
from app.stores.interfaces import ContentStore, IndexStore, PdfMappingStore

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/admin/conclusions")
def list_admin_conclusions(
    q: str = Query(default="", max_length=80),
    module: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    index_store: IndexStore = Depends(get_index_store),
):
    normalized_module = module.strip() if module else None
    LOGGER.info(
        (
            "conclusion admin list api received | request_id=%s user_id=%s "
            "q=%r module=%s page=%s page_size=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        summarize_text(q, max_length=80),
        normalized_module or "all",
        page,
        page_size,
    )

    data = SearchService.search(
        index_store=index_store,
        q=q,
        module=normalized_module,
        difficulty=None,
        tag=None,
        page=page,
        page_size=page_size,
        favorite_ids=None,
    )

    LOGGER.info(
        (
            "conclusion admin list api success | request_id=%s user_id=%s "
            "module=%s total=%s returned=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        normalized_module or "all",
        data.get("total"),
        len(data.get("items", [])) if isinstance(data.get("items"), list) else 0,
    )
    return success_response(data=data)

@router.get("/conclusions/{conclusion_id}")
def get_conclusion(
    conclusion_id: str,
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
    pdf_mapping_store: PdfMappingStore = Depends(get_pdf_mapping_store),
):
    LOGGER.info(
        "conclusion api received | request_id=%s user_id=%s conclusion_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2) if user_id else "-",
        conclusion_id,
    )

    favorite_ids = (
        FavoriteService.get_favorite_ids(db=db, user_id=user_id) if user_id else set()
    )

    data = ConclusionService.get_by_id(
        content_store=content_store,
        pdf_mapping_store=pdf_mapping_store,
        conclusion_id=conclusion_id,
        favorite_ids=favorite_ids,
    )
    LOGGER.info(
        (
            "conclusion api success | request_id=%s conclusion_id=%s pdf_available=%s "
            "is_favorited=%s"
        ),
        get_request_id(),
        conclusion_id,
        data.get("pdf_available"),
        data.get("is_favorited"),
    )
    return success_response(data=data)

