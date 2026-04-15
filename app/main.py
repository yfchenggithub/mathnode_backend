from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import app_lifespan
from app.core.logging_config import setup_logging
from app.core.request_logging_middleware import register_request_logging_middleware

setup_logging()
LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    LOGGER.info(
        "create app start | app_name=%s version=%s env=%s api_prefix=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
        settings.API_PREFIX,
    )

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Math conclusion search backend API (FastAPI + canonical JSON content)",
        lifespan=app_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    LOGGER.debug("cors middleware configured | allow_origins=%s", settings.CORS_ORIGINS)

    register_request_logging_middleware(app)
    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_PREFIX)
    LOGGER.info(
        "create app complete | route_count=%s debug_endpoints=%s",
        len(app.router.routes),
        settings.ENABLE_DEBUG_ENDPOINTS,
    )

    return app


app = create_app()
