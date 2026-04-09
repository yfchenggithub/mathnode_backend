from fastapi import APIRouter, Query

from app.core.response import success_response
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/suggest")
def suggest(q: str = Query(default="")):
    data = SearchService.suggest(q=q)
    return success_response(data=data)
