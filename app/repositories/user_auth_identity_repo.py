from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_auth_identity import UserAuthIdentity


class UserAuthIdentityRepository:
    @staticmethod
    def get_identity_by_provider_and_provider_user_id(
        db: Session, provider: str, provider_user_id: str
    ) -> UserAuthIdentity | None:
        stmt = select(UserAuthIdentity).where(
            UserAuthIdentity.provider == provider,
            UserAuthIdentity.provider_user_id == provider_user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_identity(
        db: Session,
        user_id: str,
        provider: str,
        provider_user_id: str,
        session_key: str,
        unionid: str | None = None,
        commit: bool = True,
    ) -> UserAuthIdentity:
        obj = UserAuthIdentity(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            unionid=unionid,
            session_key=session_key,
        )
        db.add(obj)
        if commit:
            db.commit()
            db.refresh(obj)
        else:
            db.flush()
        return obj

    @staticmethod
    def update_identity_session(
        db: Session,
        identity: UserAuthIdentity,
        session_key: str,
        unionid: str | None = None,
        commit: bool = True,
    ) -> UserAuthIdentity:
        identity.session_key = session_key
        if unionid:
            identity.unionid = unionid
        identity.updated_at = datetime.utcnow()

        if commit:
            db.commit()
            db.refresh(identity)
        else:
            db.flush()
        return identity
