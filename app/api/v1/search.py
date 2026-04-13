from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_index_store
from app.api.deps import get_db, get_optional_user_id
from app.core.response import success_response
from app.services.favorite_service import FavoriteService
from app.services.recent_search_service import RecentSearchService
from app.services.search_service import SearchService
from app.stores.interfaces import IndexStore

router = APIRouter()


@router.get("/search")
def search(
    q: str = Query(default=""),
    module: str | None = Query(default=None),
    difficulty: int | None = Query(default=None),
    tag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
    index_store: IndexStore = Depends(get_index_store),
):
    favorite_ids = (
        FavoriteService.get_favorite_ids(db=db, user_id=user_id) if user_id else set()
    )

    data = SearchService.search(
        index_store=index_store,
        q=q,
        module=module,
        difficulty=difficulty,
        tag=tag,
        page=page,
        page_size=page_size,
        favorite_ids=favorite_ids,
    )

    if user_id and q.strip():
        RecentSearchService.add_keyword(db=db, user_id=user_id, keyword=q.strip())

    return success_response(data=data)
