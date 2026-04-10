from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_index_store
from app.core.response import success_response
from app.services.search_service import SearchService
from app.stores.interfaces import IndexStore

router = APIRouter()


@router.get("/suggest")
def suggest(
    q: str = Query(default=""),
    index_store: IndexStore = Depends(get_index_store),
):
    data = SearchService.suggest(index_store=index_store, q=q)
    return success_response(data=data)
