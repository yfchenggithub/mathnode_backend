from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response

from app.core.logging_helpers import summarize_query_params
from app.core.request_context import bind_request_id, reset_request_id

LOGGER = logging.getLogger(__name__)


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

        LOGGER.info(
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
            if response is not None:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                log_fn = LOGGER.warning if response.status_code >= 400 else LOGGER.info
                log_fn(
                    "request end | request_id=%s method=%s path=%s status_code=%s elapsed_ms=%.2f error=%s",
                    request_id,
                    method,
                    path,
                    response.status_code,
                    elapsed_ms,
                    str(response.status_code >= 400).lower(),
                )
            reset_request_id(context_token)
