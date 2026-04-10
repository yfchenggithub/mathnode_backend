from collections.abc import Generator

from fastapi import Header

from app.core.exceptions import BizException
from app.db.session import SessionLocal


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_optional_user_id(x_token: str | None = Header(default=None)) -> str | None:
    if x_token is None:
        return None
    return get_current_user_id(x_token)


def get_current_user_id(x_token: str | None = Header(default=None)) -> str:
    if x_token == "mock-token-u1001":
        return "u1001"
    raise BizException(code=4011, message="未登录或 token 无效")
