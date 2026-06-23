from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.weekly_update_subscription import (
    WeeklyUpdateAuthorizationRequest,
    WeeklyUpdateNotificationSendRequest,
)
from app.services.weekly_update_subscription_service import (
    WeeklyUpdateSubscriptionService,
)

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/weekly-update-subscription")
def get_weekly_update_subscription(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "weekly update subscription status api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    data = WeeklyUpdateSubscriptionService.get_status(db=db, user_id=user_id)
    return success_response(data=data)


@router.post("/weekly-update-subscription/authorization")
def record_weekly_update_authorization(
    payload: WeeklyUpdateAuthorizationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "weekly update subscription authorization api received | "
            "request_id=%s user_id=%s result=%s source=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        payload.result,
        payload.source or "-",
    )
    data = WeeklyUpdateSubscriptionService.record_authorization_result(
        db=db,
        user_id=user_id,
        payload=payload,
    )
    return success_response(data=data, message="weekly update subscription saved")


@router.post("/weekly-update-subscription/unsubscribe")
def deactivate_weekly_update_subscription(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        "weekly update subscription deactivate api received | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    data = WeeklyUpdateSubscriptionService.deactivate(db=db, user_id=user_id)
    return success_response(data=data, message="weekly update subscription disabled")


@router.post("/admin/weekly-update-notifications/send")
def send_weekly_update_notifications(
    payload: WeeklyUpdateNotificationSendRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "weekly update notification send api received | request_id=%s "
            "user_id=%s project_name=%r progress=%r limit=%s"
        ),
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
        payload.project_name,
        payload.project_progress,
        payload.limit,
    )
    data = WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers(
        db=db,
        payload=payload,
    )
    return success_response(data=data, message="weekly update notifications sent")
