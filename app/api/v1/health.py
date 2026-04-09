from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("/health")
def health_check():
    return success_response(
        data={
            "status": "ok",
            "db": "mock",
            "typesense": "mock",
            "redis": "mock",
        }
    )
