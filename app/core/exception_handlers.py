from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging_helpers import summarize_query_params, summarize_validation_errors
from app.core.request_context import get_request_id
from app.core.response import error_response

LOGGER = logging.getLogger(__name__)


def _request_id_from_request(request: Request) -> str:
    state_request_id = getattr(request.state, "request_id", None)
    if isinstance(state_request_id, str) and state_request_id.strip():
        return state_request_id
    return get_request_id()


def _derive_error_code_from_status(status_code: int) -> int:
    if status_code == 404:
        return 4040
    if status_code == 422:
        return 4220
    if status_code >= 500:
        return 5000
    if status_code >= 400:
        return status_code * 10
    return status_code


def _normalize_http_detail(detail: object, status_code: int) -> str:
    if isinstance(detail, str):
        text = detail.strip()
        if text:
            return text
    return f"HTTP {status_code}"


def _error_json_response(
    *,
    status_code: int,
    code: int,
    message: str,
    request_id: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code=code, message=message),
        headers={"X-Request-ID": request_id},
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = _request_id_from_request(request)
    errors = exc.errors()
    error_summary = summarize_validation_errors(errors)

    LOGGER.warning(
        "request validation failed | request_id=%s method=%s path=%s query=%s error_count=%s errors=%s",
        request_id,
        request.method,
        request.url.path,
        summarize_query_params(dict(request.query_params)),
        len(errors),
        error_summary,
    )

    return _error_json_response(
        status_code=422,
        code=4220,
        message="request validation failed",
        request_id=request_id,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    request_id = _request_id_from_request(request)
    status_code = exc.status_code
    message = _normalize_http_detail(exc.detail, status_code=status_code)
    code = _derive_error_code_from_status(status_code)

    log_message = (
        "http exception | request_id=%s method=%s path=%s status_code=%s code=%s detail=%s"
    )

    if status_code >= 500:
        LOGGER.error(
            log_message,
            request_id,
            request.method,
            request.url.path,
            status_code,
            code,
            message,
        )
    elif status_code == 404:
        LOGGER.info(
            log_message,
            request_id,
            request.method,
            request.url.path,
            status_code,
            code,
            message,
        )
    else:
        LOGGER.warning(
            log_message,
            request_id,
            request.method,
            request.url.path,
            status_code,
            code,
            message,
        )

    return _error_json_response(
        status_code=status_code,
        code=code,
        message=message,
        request_id=request_id,
    )


async def app_error_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = _request_id_from_request(request)

    log_message = (
        "app error | request_id=%s method=%s path=%s status_code=%s code=%s message=%s"
    )
    if exc.status_code >= 500:
        LOGGER.error(
            log_message,
            request_id,
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
        )
    else:
        LOGGER.warning(
            log_message,
            request_id,
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
        )

    return _error_json_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=request_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id_from_request(request)
    LOGGER.exception(
        "unhandled exception | request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    return _error_json_response(
        status_code=500,
        code=5000,
        message="服务器内部错误",
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(AppError, app_error_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
