"""Application-level exception classes.

`exceptions.py` is intentionally focused on exception definitions only.
FastAPI exception handlers live in `app/core/exception_handlers.py`.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base exception for expected application/business errors."""

    def __init__(
        self,
        code: int = 4000,
        message: str = "business error",
        *,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(message)


class BizException(AppError):
    """Backwards-compatible business exception used across services."""

    def __init__(
        self,
        code: int = 4000,
        message: str = "business error",
        *,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            extra=extra,
        )


class NotFoundError(AppError):
    def __init__(self, message: str = "resource not found", code: int = 4040) -> None:
        super().__init__(code=code, message=message, status_code=404)


class AuthError(AppError):
    def __init__(self, message: str = "unauthorized", code: int = 4011) -> None:
        super().__init__(code=code, message=message, status_code=401)
