import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.seed_conclusions import SEED_CONCLUSIONS
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.conclusion import Conclusion
from app.models.favorite import Favorite
from app.models.recent_search import RecentSearch
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity

LOGGER = logging.getLogger(__name__)


def seed_conclusions_if_empty(db: Session) -> None:
    stmt = select(Conclusion).limit(1)
    exists = db.execute(stmt).scalar_one_or_none()
    if exists:
        LOGGER.debug("seed skipped | conclusions already exist")
        return

    for item in SEED_CONCLUSIONS:
        db.add(Conclusion(**item))

    db.commit()
    LOGGER.info("seed completed | inserted=%s", len(SEED_CONCLUSIONS))


def init_db() -> None:
    LOGGER.debug("db init start")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_conclusions_if_empty(db)
    finally:
        db.close()
    LOGGER.info("db init complete")
