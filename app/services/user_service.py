from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BizException, NotFoundError
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserStatus

LOGGER = logging.getLogger(__name__)

VALID_USER_STATUSES: set[str] = {User.STATUS_ACTIVE, User.STATUS_DISABLED}


class UserService:
    @staticmethod
    def _normalize_text(value: str | None, max_length: int) -> str:
        text = (value or "").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length]

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        normalized = (status or "").strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_USER_STATUSES:
            raise BizException(
                code=4223,
                message="invalid user status",
                status_code=422,
            )
        return normalized

    @staticmethod
    def ensure_active(user: User) -> None:
        if user.status != User.STATUS_DISABLED:
            return

        LOGGER.warning(
            "disabled user rejected | request_id=%s user_id=%s",
            get_request_id(),
            mask_sensitive(user.id, left=2, right=2),
        )
        raise BizException(
            code=4031,
            message="account disabled",
            status_code=403,
        )

    @staticmethod
    def serialize(user: User) -> dict:
        return {
            "id": user.id,
            "user_id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "status": user.status,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat()
            if user.last_login_at
            else None,
        }

    @staticmethod
    def get_profile(user: User) -> dict:
        UserService.ensure_active(user)
        return UserService.serialize(user)

    @staticmethod
    def list_users(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_status = UserService._normalize_status(status)
        rows, total = UserRepository.list_users(
            db,
            status=normalized_status,
            keyword=UserService._normalize_text(keyword, 80),
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [UserService.serialize(row) for row in rows],
        }

    @staticmethod
    def update_status(
        db: Session,
        *,
        user_id: str,
        status: UserStatus,
    ) -> dict:
        normalized_status = UserService._normalize_status(status)
        if normalized_status is None:
            raise BizException(
                code=4223,
                message="invalid user status",
                status_code=422,
            )

        user = UserRepository.get_user_by_id(db=db, user_id=user_id)
        if user is None:
            raise NotFoundError(message="user not found")

        updated = UserRepository.update_status(db, user, normalized_status)
        return UserService.serialize(updated)
