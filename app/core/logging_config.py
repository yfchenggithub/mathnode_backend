from __future__ import annotations

import logging
import logging.config
from typing import Any

from app.core.config import settings

_LOGGING_CONFIGURED = False
_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
_VALID_LOG_FORMATS = {"standard", "detailed"}


def _normalize_log_level(raw_level: str | None, fallback: str = "INFO") -> str:
    level = (raw_level or "").strip().upper()
    if level in _VALID_LOG_LEVELS:
        return level

    normalized_fallback = (fallback or "INFO").strip().upper()
    if normalized_fallback in _VALID_LOG_LEVELS:
        return normalized_fallback
    return "INFO"


def _normalize_log_format(raw_format: str | None, fallback: str = "detailed") -> str:
    formatter = (raw_format or "").strip().lower()
    if formatter in _VALID_LOG_FORMATS:
        return formatter

    normalized_fallback = (fallback or "detailed").strip().lower()
    if normalized_fallback in _VALID_LOG_FORMATS:
        return normalized_fallback
    return "detailed"


def _build_formatters() -> dict[str, dict[str, str]]:
    return {
        "standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        },
        "detailed": {
            "format": (
                "%(asctime)s | %(levelname)-8s | %(name)s | "
                "%(filename)s:%(lineno)d | %(message)s"
            )
        },
    }


def _build_console_handler(formatter_name: str) -> dict[str, str]:
    return {
        "class": "logging.StreamHandler",
        "formatter": formatter_name,
        "level": "NOTSET",
    }


def _build_null_handler() -> dict[str, str]:
    return {
        "class": "logging.NullHandler",
    }


def _resolve_http_client_log_level(
    *,
    third_party_log_level: str,
    http_client_debug: bool,
) -> str:
    if http_client_debug:
        return "DEBUG"
    return third_party_log_level


def _build_logger_configs(
    *,
    app_log_level: str,
    third_party_log_level: str,
    uvicorn_log_level: str,
    uvicorn_access_log: bool,
    http_client_log_level: str,
) -> dict[str, dict[str, Any]]:
    logger_configs: dict[str, dict[str, Any]] = {
        "app": {
            "handlers": ["console"],
            "level": app_log_level,
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": uvicorn_log_level,
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["console"],
            "level": uvicorn_log_level,
            "propagate": False,
        },
        "httpx": {
            "handlers": [],
            "level": http_client_log_level,
            "propagate": True,
        },
        "httpcore": {
            "handlers": [],
            "level": http_client_log_level,
            "propagate": True,
        },
        "fastapi": {
            "handlers": [],
            "level": third_party_log_level,
            "propagate": True,
        },
        "asyncio": {
            "handlers": [],
            "level": third_party_log_level,
            "propagate": True,
        },
    }

    if uvicorn_access_log:
        logger_configs["uvicorn.access"] = {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        }
    else:
        logger_configs["uvicorn.access"] = {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        }
    return logger_configs


def setup_logging(force: bool = False) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED and not force:
        return

    formatter_name = _normalize_log_format(
        settings.LOG_FORMAT,
        fallback="detailed",
    )
    global_log_level = _normalize_log_level(settings.LOG_LEVEL, fallback="INFO")
    app_log_level = _normalize_log_level(settings.APP_LOG_LEVEL, fallback=global_log_level)
    third_party_log_level = _normalize_log_level(
        settings.THIRD_PARTY_LOG_LEVEL,
        fallback=global_log_level,
    )
    uvicorn_log_level = _normalize_log_level(
        settings.UVICORN_LOG_LEVEL,
        fallback=global_log_level,
    )

    if not settings.LOG_ENABLED:
        app_log_level = "ERROR"
        third_party_log_level = "ERROR"
        uvicorn_log_level = "ERROR"
        uvicorn_access_log = False
    else:
        uvicorn_access_log = settings.UVICORN_ACCESS_LOG

    http_client_log_level = _resolve_http_client_log_level(
        third_party_log_level=third_party_log_level,
        http_client_debug=settings.HTTP_CLIENT_DEBUG and settings.LOG_ENABLED,
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": _build_formatters(),
            "handlers": {
                "console": _build_console_handler(formatter_name),
                "null": _build_null_handler(),
            },
            "root": {
                "handlers": ["console"],
                "level": third_party_log_level,
            },
            "loggers": _build_logger_configs(
                app_log_level=app_log_level,
                third_party_log_level=third_party_log_level,
                uvicorn_log_level=uvicorn_log_level,
                uvicorn_access_log=uvicorn_access_log,
                http_client_log_level=http_client_log_level,
            ),
        }
    )
    _LOGGING_CONFIGURED = True
