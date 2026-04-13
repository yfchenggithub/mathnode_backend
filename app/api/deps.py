from collections.abc import Generator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService

MOCK_TOKEN = "mock-token-u1001"
MOCK_USER_ID = "u1001"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    raw = authorization.strip()
    if not raw:
        return None

    parts = raw.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise BizException(code=4011, message="unauthorized")

    token = parts[1].strip()
    if not token:
        raise BizException(code=4011, message="unauthorized")
    return token


def get_access_token(
    authorization: str | None = Header(default=None),
    x_token: str | None = Header(default=None),
) -> str | None:
    bearer_token = _extract_bearer_token(authorization)
    if bearer_token is not None:
        return bearer_token

    if x_token is None:
        return None

    normalized = x_token.strip()
    return normalized or None


def _resolve_user_id_from_token(token: str) -> str:
    if token == MOCK_TOKEN:
        return MOCK_USER_ID
    return AuthService.parse_access_token(token)


def get_optional_user_id(token: str | None = Depends(get_access_token)) -> str | None:
    if token is None:
        return None
    return _resolve_user_id_from_token(token)


def get_current_user_id(token: str | None = Depends(get_access_token)) -> str:
    if token is None:
        raise BizException(code=4011, message="unauthorized")
    return _resolve_user_id_from_token(token)


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = UserRepository.get_user_by_id(db=db, user_id=user_id)
    if user is None:
        raise BizException(code=4011, message="unauthorized")
    return user


def get_current_user_optional(
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
) -> User | None:
    if user_id is None:
        return None
    return UserRepository.get_user_by_id(db=db, user_id=user_id)
