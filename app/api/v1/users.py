from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.models.user import User
from app.schemas.user import UserStatusUpdateRequest
from app.services.user_service import UserService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/users/me")
def get_me(current_user: User = Depends(get_current_user)):
    LOGGER.info(
        "user profile api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(current_user.id, left=2, right=2),
    )
    data = UserService.get_profile(current_user)
    LOGGER.info(
        "user profile api success | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(current_user.id, left=2, right=2),
    )
    return success_response(data=data)


@router.get("/users")
def list_users(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(active|disabled)$",
    ),
    keyword: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "user list api received | request_id=%s user_id=%s status=%s "
            "keyword=%r page=%s page_size=%s"
        ),
        get_request_id(),
        mask_sensitive(current_user_id, left=2, right=2),
        status_filter or "all",
        summarize_text(keyword or "", max_length=80),
        page,
        page_size,
    )
    data = UserService.list_users(
        db=db,
        status=status_filter,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    LOGGER.info(
        "user list api success | request_id=%s user_id=%s total=%s",
        get_request_id(),
        mask_sensitive(current_user_id, left=2, right=2),
        data.get("total"),
    )
    return success_response(data=data)


@router.put("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "user status update api received | request_id=%s user_id=%s "
            "target_user_id=%s status=%s"
        ),
        get_request_id(),
        mask_sensitive(current_user_id, left=2, right=2),
        mask_sensitive(user_id, left=2, right=2),
        payload.status,
    )
    data = UserService.update_status(
        db=db,
        user_id=user_id,
        status=payload.status,
    )
    LOGGER.info(
        (
            "user status update api success | request_id=%s user_id=%s "
            "target_user_id=%s status=%s"
        ),
        get_request_id(),
        mask_sensitive(current_user_id, left=2, right=2),
        mask_sensitive(user_id, left=2, right=2),
        data.get("status"),
    )
    return success_response(data=data, message="user status updated")
