from fastapi import APIRouter, Header, Query

from app.core.response import success_response
from app.services.favorite_service import FavoriteService
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/search")
def search(
    q: str = Query(default=""),
    module: str | None = Query(default=None),
    difficulty: int | None = Query(default=None),
    tag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    x_token: str | None = Header(default=None),
):
    user_id = "u1001" if x_token == "mock-token-u1001" else None
    favorite_ids = FavoriteService.get_favorite_ids(user_id) if user_id else set()

    data = SearchService.search(
        q=q,
        module=module,
        difficulty=difficulty,
        tag=tag,
        page=page,
        page_size=page_size,
        favorite_ids=favorite_ids,
    )
    return success_response(data=data)
