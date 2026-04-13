from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_content_store, get_pdf_mapping_store
from app.api.deps import get_db, get_optional_user_id
from app.core.response import success_response
from app.services.conclusion_service import ConclusionService
from app.services.favorite_service import FavoriteService
from app.stores.interfaces import ContentStore, PdfMappingStore

router = APIRouter()


@router.get("/conclusions/{conclusion_id}")
def get_conclusion(
    conclusion_id: str,
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
    content_store: ContentStore = Depends(get_content_store),
    pdf_mapping_store: PdfMappingStore = Depends(get_pdf_mapping_store),
):
    favorite_ids = (
        FavoriteService.get_favorite_ids(db=db, user_id=user_id) if user_id else set()
    )

    data = ConclusionService.get_by_id(
        content_store=content_store,
        pdf_mapping_store=pdf_mapping_store,
        conclusion_id=conclusion_id,
        favorite_ids=favorite_ids,
    )
    return success_response(data=data)
