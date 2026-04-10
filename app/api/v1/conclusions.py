from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store
from app.api.deps import get_db
from app.core.response import success_response
from app.services.conclusion_service import ConclusionService
from app.services.favorite_service import FavoriteService
from app.stores.interfaces import ContentStore

router = APIRouter()


@router.get("/conclusions/{conclusion_id}")
def get_conclusion(
    conclusion_id: str,
    x_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
):
    user_id = "u1001" if x_token == "mock-token-u1001" else None
    favorite_ids = (
        FavoriteService.get_favorite_ids(db=db, user_id=user_id) if user_id else set()
    )

    data = ConclusionService.get_by_id(
        content_store=content_store,
        conclusion_id=conclusion_id,
        favorite_ids=favorite_ids,
    )
    return success_response(data=data)
