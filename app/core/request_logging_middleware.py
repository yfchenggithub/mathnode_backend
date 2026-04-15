from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response

from app.core.config import settings
from app.core.logging_helpers import summarize_query_params
from app.core.request_context import bind_request_id, reset_request_id

LOGGER = logging.getLogger(__name__)
_VALID_LOG_LEVEL_NAMES = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _normalize_log_level_name(raw_level: str | None, fallback: str = "INFO") -> str:
    level_name = (raw_level or "").strip().upper()
    if level_name in _VALID_LOG_LEVEL_NAMES:
        return level_name

    fallback_name = (fallback or "INFO").strip().upper()
    if fallback_name in _VALID_LOG_LEVEL_NAMES:
        return fallback_name
    return "INFO"


def _resolve_request_log_level() -> int:
    level_name = _normalize_log_level_name(
        settings.REQUEST_LOG_LEVEL,
        fallback=settings.APP_LOG_LEVEL,
    )
    return logging.getLevelNamesMapping().get(level_name, logging.INFO)


def _resolve_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host
    return "-"


def _build_request_id() -> str:
    return uuid.uuid4().hex[:8]


def register_request_logging_middleware(app: FastAPI) -> None:
    request_log_enabled = settings.LOG_ENABLED and settings.REQUEST_LOG_ENABLED
    request_log_level = _resolve_request_log_level()

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        started_at = time.perf_counter()
        request_id = _build_request_id()
        request.state.request_id = request_id
        context_token = bind_request_id(request_id)

        method = request.method
        path = request.url.path
        query_summary = summarize_query_params(dict(request.query_params))
        client_ip = _resolve_client_ip(request)

        if request_log_enabled:
            LOGGER.log(
                request_log_level,
                "request start | request_id=%s method=%s path=%s query=%s client_ip=%s",
                request_id,
                method,
                path,
                query_summary,
                client_ip,
            )

        response: Response | None = None

        try:
            response = await call_next(request)
            response.headers.setdefault("X-Request-ID", request_id)
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            LOGGER.exception(
                "request failed | request_id=%s method=%s path=%s elapsed_ms=%.2f error=true",
                request_id,
                method,
                path,
                elapsed_ms,
            )
            raise
        finally:
            if response is not None and request_log_enabled:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                end_log_level = request_log_level
                if response.status_code >= 500 and end_log_level < logging.WARNING:
                    end_log_level = logging.WARNING

                LOGGER.log(
                    end_log_level,
                    "request end | request_id=%s method=%s path=%s status_code=%s elapsed_ms=%.2f error=%s",
                    request_id,
                    method,
                    path,
                    response.status_code,
                    elapsed_ms,
                    str(response.status_code >= 400).lower(),
                )
            reset_request_id(context_token)
