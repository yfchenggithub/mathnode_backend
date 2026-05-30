from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store
from app.api.dependencies import get_pdf_mapping_store
from app.api.deps import get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.favorite import FavoriteCreateRequest
from app.schemas.favorite_handout import FavoriteHandoutCreateRequest
from app.services.favorite_handout_service import FavoriteHandoutService
from app.services.favorite_service import FavoriteService
from app.stores.interfaces import ContentStore, PdfMappingStore

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


@router.post("/favorites/handouts", status_code=201)
def create_favorite_handout(
    payload: FavoriteHandoutCreateRequest | None = Body(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
    pdf_mapping_store: PdfMappingStore = Depends(get_pdf_mapping_store),
):
    del payload
    LOGGER.info(
        "favorite handout create api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    data = FavoriteHandoutService.create_from_current_user_favorites(
        db=db,
        user_id=user_id,
        content_store=content_store,
        pdf_mapping_store=pdf_mapping_store,
    )
    LOGGER.info(
        "favorite handout create api success | request_id=%s user_id=%s handout_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("handout_id"),
    )
    return success_response(data=data)


@router.get("/favorites/handouts/{handout_id}")
def get_favorite_handout(
    handout_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "favorite handout get api received | request_id=%s user_id=%s handout_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        handout_id,
    )
    data = FavoriteHandoutService.get_handout(
        db=db,
        user_id=user_id,
        handout_id=handout_id,
    )
    LOGGER.info(
        "favorite handout get api success | request_id=%s user_id=%s handout_id=%s status=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        handout_id,
        data.get("status"),
    )
    return success_response(data=data)


@router.get("/favorites/handouts/{handout_id}/pdf", response_class=FileResponse)
def download_favorite_handout_pdf(
    handout_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "favorite handout pdf api received | request_id=%s user_id=%s handout_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        handout_id,
    )
    file_info = FavoriteHandoutService.get_handout_pdf(
        db=db,
        user_id=user_id,
        handout_id=handout_id,
    )
    LOGGER.info(
        "favorite handout pdf api success | request_id=%s user_id=%s handout_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        handout_id,
    )
    return FileResponse(
        path=str(file_info.absolute_path),
        media_type="application/pdf",
        filename=file_info.filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
