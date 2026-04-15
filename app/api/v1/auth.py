import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.core.response import success_response
from app.schemas.auth import LoginRequest, WechatMiniAppLoginRequest
from app.services.auth_service import AuthService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/auth/login")
def login(payload: LoginRequest):
    LOGGER.info(
        "auth login api received | request_id=%s platform=mock code=%r",
        get_request_id(),
        mask_sensitive(payload.code, left=2, right=2),
    )
    data = AuthService.login(code=payload.code)
    LOGGER.info(
        "auth login api success | request_id=%s user_id=%s",
        get_request_id(),
        data.get("user_id"),
    )
    return success_response(data=data, message="login success")


@router.post("/auth/wechat-miniapp-login")
def wechat_miniapp_login(
    payload: WechatMiniAppLoginRequest,
    db: Session = Depends(get_db),
):
    LOGGER.info(
        (
            "auth wechat login api received | request_id=%s platform=wechat_miniapp "
            "nickname_present=%s avatar_present=%s"
        ),
        get_request_id(),
        str(bool(payload.nickname)).lower(),
        str(bool(payload.avatar_url)).lower(),
    )
    data = AuthService.login_by_wechat_miniapp_code(
        db=db,
        code=payload.code,
        nickname=payload.nickname,
        avatar_url=payload.avatar_url,
    )
    LOGGER.info(
        "auth wechat login api success | request_id=%s user_id=%s",
        get_request_id(),
        data.get("user_id"),
    )
    return success_response(data=data, message="login success")
