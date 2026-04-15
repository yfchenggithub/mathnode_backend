from collections.abc import Generator
import logging

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService

MOCK_TOKEN = "mock-token-u1001"
MOCK_USER_ID = "u1001"
LOGGER = logging.getLogger(__name__)


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
        LOGGER.warning(
            "token parse failed | request_id=%s reason=invalid_authorization_prefix",
            get_request_id(),
        )
        raise BizException(code=4011, message="unauthorized")

    token = parts[1].strip()
    if not token:
        LOGGER.warning(
            "token parse failed | request_id=%s reason=empty_bearer_token",
            get_request_id(),
        )
        raise BizException(code=4011, message="unauthorized")
    return token


def get_access_token(
    authorization: str | None = Header(default=None),
    x_token: str | None = Header(default=None),
) -> str | None:
    bearer_token = _extract_bearer_token(authorization)
    if bearer_token is not None:
        LOGGER.debug(
            "token extracted from authorization | request_id=%s token=%s",
            get_request_id(),
            mask_sensitive(bearer_token),
        )
        return bearer_token

    if x_token is None:
        return None

    normalized = x_token.strip()
    if normalized:
        LOGGER.debug(
            "token extracted from x-token | request_id=%s token=%s",
            get_request_id(),
            mask_sensitive(normalized),
        )
    return normalized or None


def _resolve_user_id_from_token(token: str) -> str:
    if token == MOCK_TOKEN:
        LOGGER.debug(
            "token resolved via mock token | request_id=%s",
            get_request_id(),
        )
        return MOCK_USER_ID
    user_id = AuthService.parse_access_token(token)
    LOGGER.debug(
        "token resolved to user_id | request_id=%s user_id=%s",
        get_request_id(),
        mask_sensitive(user_id, left=2, right=2),
    )
    return user_id


def get_optional_user_id(token: str | None = Depends(get_access_token)) -> str | None:
    if token is None:
        return None
    return _resolve_user_id_from_token(token)


def get_current_user_id(token: str | None = Depends(get_access_token)) -> str:
    if token is None:
        LOGGER.warning(
            "auth required but token missing | request_id=%s",
            get_request_id(),
        )
        raise BizException(code=4011, message="unauthorized")
    return _resolve_user_id_from_token(token)


def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = UserRepository.get_user_by_id(db=db, user_id=user_id)
    if user is None:
        LOGGER.warning(
            "current user not found | request_id=%s user_id=%s",
            get_request_id(),
            mask_sensitive(user_id, left=2, right=2),
        )
        raise BizException(code=4011, message="unauthorized")
    return user


def get_current_user_optional(
    user_id: str | None = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
) -> User | None:
    if user_id is None:
        return None
    return UserRepository.get_user_by_id(db=db, user_id=user_id)
