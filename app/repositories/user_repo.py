from datetime import datetime
from uuid import uuid4

from sqlalchemy import desc, func, or_, select
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
    def list_users(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        conditions = []

        if status:
            conditions.append(User.status == status)

        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            conditions.append(
                or_(
                    User.id.like(keyword_pattern),
                    User.nickname.like(keyword_pattern),
                )
            )

        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = int(db.execute(count_stmt).scalar_one() or 0)
        offset = max(0, page - 1) * page_size
        rows = (
            db.execute(
                stmt.order_by(
                    desc(User.created_at),
                    desc(User.id),
                )
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(rows), total

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
    def update_status(
        db: Session,
        user: User,
        status: str,
    ) -> User:
        user.status = status
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user

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
