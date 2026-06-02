from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, get_optional_user_id
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.conclusion_request import (
    ConclusionRequestCreateRequest,
    ConclusionRequestUpdateRequest,
)
from app.services.conclusion_request_service import ConclusionRequestService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/conclusion-requests", status_code=status.HTTP_201_CREATED)
def create_conclusion_request(
    payload: ConclusionRequestCreateRequest,
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "conclusion request create api received | request_id=%s user_id=%s query=%r",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2) if user_id else "anonymous",
        summarize_text(payload.query, max_length=80),
    )
    data = ConclusionRequestService.create_request(
        db=db,
        user_id=user_id,
        payload=payload,
    )
    LOGGER.info(
        "conclusion request create api success | request_id=%s user_id=%s id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2) if user_id else "anonymous",
        data.get("id"),
    )
    return success_response(data=data, message="conclusion request submitted")


@router.get("/admin/conclusion-requests")
def list_conclusion_requests(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|updated|ignored)$",
    ),
    keyword: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "conclusion request admin list api received | request_id=%s "
            "user_id=%s status=%s page=%s page_size=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        status_filter or "all",
        page,
        page_size,
    )
    data = ConclusionRequestService.list_requests(
        db=db,
        status=status_filter,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    LOGGER.info(
        (
            "conclusion request admin list api success | request_id=%s "
            "user_id=%s total=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)


@router.put("/admin/conclusion-requests/{request_id}")
def update_conclusion_request_status(
    request_id: int,
    payload: ConclusionRequestUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "conclusion request admin update api received | request_id=%s "
            "user_id=%s target_id=%s status=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        request_id,
        payload.status,
    )
    data = ConclusionRequestService.update_status(
        db=db,
        request_id=request_id,
        status=payload.status,
    )
    LOGGER.info(
        (
            "conclusion request admin update api success | request_id=%s "
            "user_id=%s target_id=%s status=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        request_id,
        data.get("status"),
    )
    return success_response(data=data, message="status updated")