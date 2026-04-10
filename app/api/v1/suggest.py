from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import success_response
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/suggest")
def suggest(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    data = SearchService.suggest(db=db, q=q)
    return success_response(data=data)
