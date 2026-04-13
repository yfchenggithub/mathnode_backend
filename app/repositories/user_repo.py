from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    @staticmethod
    def _generate_user_id() -> str:
        return f"u{uuid4().hex[:12]}"

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_user(
        db: Session,
        nickname: str,
        avatar_url: str | None = None,
        commit: bool = True,
    ) -> User:
        obj = User(
            id=UserRepository._generate_user_id(),
            nickname=nickname,
            avatar_url=avatar_url,
            last_login_at=datetime.utcnow(),
        )
        db.add(obj)
        if commit:
            db.commit()
            db.refresh(obj)
        else:
            db.flush()
        return obj

    @staticmethod
    def touch_last_login(
        db: Session,
        user: User,
        nickname: str | None = None,
        avatar_url: str | None = None,
        commit: bool = True,
    ) -> User:
        user.last_login_at = datetime.utcnow()

        if nickname is not None:
            cleaned_nickname = nickname.strip()
            if cleaned_nickname:
                user.nickname = cleaned_nickname

        if avatar_url is not None:
            cleaned_avatar_url = avatar_url.strip()
            user.avatar_url = cleaned_avatar_url or None

        if commit:
            db.commit()
            db.refresh(user)
        else:
            db.flush()
        return user
