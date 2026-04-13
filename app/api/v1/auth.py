from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import success_response
from app.schemas.auth import LoginRequest, WechatMiniAppLoginRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest):
    data = AuthService.login(code=payload.code)
    return success_response(data=data, message="login success")


@router.post("/auth/wechat-miniapp-login")
def wechat_miniapp_login(
    payload: WechatMiniAppLoginRequest,
    db: Session = Depends(get_db),
):
    data = AuthService.login_by_wechat_miniapp_code(
        db=db,
        code=payload.code,
        nickname=payload.nickname,
        avatar_url=payload.avatar_url,
    )
    return success_response(data=data, message="login success")
