from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.core.response import success_response
from app.services.recent_search_service import RecentSearchService

router = APIRouter()


@router.get("/recent-searches")
def list_recent_searches(
    limit: int = Query(default=10, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data = RecentSearchService.list_recent(db=db, user_id=user_id, limit=limit)
    return success_response(data=data)


@router.delete("/recent-searches")
def clear_recent_searches(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    RecentSearchService.clear_all(db=db, user_id=user_id)
    return success_response(message="最近搜索已清空")
