from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, get_optional_user_id
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.correction_report import CorrectionReportCreateRequest
from app.services.correction_report_service import CorrectionReportService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/correction-reports", status_code=status.HTTP_201_CREATED)
def create_correction_report(
    payload: CorrectionReportCreateRequest,
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "correction report create api received | request_id=%s user_id=%s "
            "conclusion_id=%r title=%r"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2) if user_id else "anonymous",
        payload.conclusion_id,
        summarize_text(payload.conclusion_title, max_length=80),
    )
    data = CorrectionReportService.create_report(
        db=db,
        user_id=user_id,
        payload=payload,
    )
    LOGGER.info(
        "correction report create api success | request_id=%s user_id=%s id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2) if user_id else "anonymous",
        data.get("id"),
    )
    return success_response(data=data, message="correction report submitted")


@router.get("/admin/correction-reports")
def list_correction_reports(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|reviewed|ignored)$",
    ),
    keyword: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "correction report admin list api received | request_id=%s "
            "user_id=%s status=%s page=%s page_size=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        status_filter or "all",
        page,
        page_size,
    )
    data = CorrectionReportService.list_reports(
        db=db,
        status=status_filter,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    LOGGER.info(
        (
            "correction report admin list api success | request_id=%s "
            "user_id=%s total=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)
