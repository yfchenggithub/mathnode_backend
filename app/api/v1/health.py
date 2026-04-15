import logging

from fastapi import APIRouter

from app.core.request_context import get_request_id
from app.core.response import success_response

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    LOGGER.debug("health check | request_id=%s", get_request_id())
    return success_response(
        data={
            "status": "ok",
            "db": "mock",
            "typesense": "mock",
            "redis": "mock",
        }
    )
