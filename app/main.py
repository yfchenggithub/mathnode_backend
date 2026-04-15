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

# Configure logging at import time so startup/bootstrap logs are captured
# both in `uvicorn app.main:app` and process managers (for example systemd).
setup_logging()
LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    LOGGER.info(
        (
            "create app start | app_name=%s version=%s env=%s api_prefix=%s "
            "log_enabled=%s app_log_level=%s third_party_log_level=%s "
            "uvicorn_access_log=%s request_log_enabled=%s request_log_level=%s"
        ),
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
        settings.API_PREFIX,
        str(settings.LOG_ENABLED).lower(),
        settings.APP_LOG_LEVEL,
        settings.THIRD_PARTY_LOG_LEVEL,
        str(settings.UVICORN_ACCESS_LOG).lower(),
        str(settings.REQUEST_LOG_ENABLED).lower(),
        settings.REQUEST_LOG_LEVEL,
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
