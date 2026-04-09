from fastapi import APIRouter, Header

from app.core.exceptions import BizException
from app.core.response import success_response
from app.schemas.favorite import FavoriteCreateRequest
from app.services.favorite_service import FavoriteService

router = APIRouter()


def _get_current_user_id(x_token: str | None) -> str:
    if x_token == "mock-token-u1001":
        return "u1001"
    raise BizException(code=4011, message="未登录或 token 无效")


@router.post("/favorites")
def add_favorite(
    payload: FavoriteCreateRequest, x_token: str | None = Header(default=None)
):
    user_id = _get_current_user_id(x_token)
    FavoriteService.add_favorite(user_id=user_id, conclusion_id=payload.conclusion_id)
    return success_response(message="收藏成功")


@router.delete("/favorites/{conclusion_id}")
def remove_favorite(conclusion_id: str, x_token: str | None = Header(default=None)):
    user_id = _get_current_user_id(x_token)
    FavoriteService.remove_favorite(user_id=user_id, conclusion_id=conclusion_id)
    return success_response(message="取消收藏成功")


@router.get("/favorites")
def list_favorites(x_token: str | None = Header(default=None)):
    user_id = _get_current_user_id(x_token)
    data = FavoriteService.list_favorites(user_id=user_id)
    return success_response(data=data)
