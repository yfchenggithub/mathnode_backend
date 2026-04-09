from fastapi import APIRouter, Header

from app.core.response import success_response
from app.services.conclusion_service import ConclusionService
from app.services.favorite_service import FavoriteService

router = APIRouter()


@router.get("/conclusions/{conclusion_id}")
def get_conclusion(conclusion_id: str, x_token: str | None = Header(default=None)):
    user_id = "u1001" if x_token == "mock-token-u1001" else None
    favorite_ids = FavoriteService.get_favorite_ids(user_id) if user_id else set()

    data = ConclusionService.get_by_id(
        conclusion_id=conclusion_id, favorite_ids=favorite_ids
    )
    return success_response(data=data)
