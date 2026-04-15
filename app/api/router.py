from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.conclusions import router as conclusions_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.health import router as health_router
from app.api.v1.pdfs import router as pdfs_router
from app.api.v1.recent_searches import router as recent_searches_router
from app.api.v1.search import router as search_router
from app.api.v1.suggest import router as suggest_router
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(search_router, tags=["search"])
api_router.include_router(suggest_router, tags=["suggest"])
api_router.include_router(conclusions_router, tags=["conclusions"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(favorites_router, tags=["favorites"])
api_router.include_router(recent_searches_router, tags=["recent_searches"])
api_router.include_router(pdfs_router, tags=["pdfs"])

if settings.ENABLE_DEBUG_ENDPOINTS:
    from app.api.debug import router as debug_router

    api_router.include_router(debug_router, tags=["debug"])
