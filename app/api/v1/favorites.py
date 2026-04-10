from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store
from app.api.deps import get_current_user_id, get_db
from app.core.response import success_response
from app.schemas.favorite import FavoriteCreateRequest
from app.services.favorite_service import FavoriteService
from app.stores.interfaces import ContentStore

router = APIRouter()


@router.post("/favorites")
def add_favorite(
    payload: FavoriteCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
):
    FavoriteService.add_favorite(
        db=db,
        user_id=user_id,
        conclusion_id=payload.conclusion_id,
        content_store=content_store,
    )
    return success_response(message="收藏成功")


@router.delete("/favorites/{conclusion_id}")
def remove_favorite(
    conclusion_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    FavoriteService.remove_favorite(db=db, user_id=user_id, conclusion_id=conclusion_id)
    return success_response(message="取消收藏成功")


@router.get("/favorites")
def list_favorites(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
):
    data = FavoriteService.list_favorites(
        db=db,
        user_id=user_id,
        content_store=content_store,
    )
    return success_response(data=data)
