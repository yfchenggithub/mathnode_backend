from __future__ import annotations

from contextvars import ContextVar, Token

_REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID_VAR.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID_VAR.reset(token)


def get_request_id(default: str = "-") -> str:
    request_id = _REQUEST_ID_VAR.get()
    if request_id:
        return request_id
    return default
