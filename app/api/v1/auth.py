from fastapi import APIRouter

from app.core.response import success_response
from app.schemas.auth import LoginRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest):
    data = AuthService.login(code=payload.code)
    return success_response(data=data, message="登录成功")
