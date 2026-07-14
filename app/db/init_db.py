import logging

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.data.seed_conclusions import SEED_CONCLUSIONS
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.conclusion import Conclusion
from app.models.conclusion_request import ConclusionRequest
from app.models.conclusion_view_stat import ConclusionViewStat
from app.models.correction_report import CorrectionReport
from app.models.favorite import Favorite
from app.models.favorite_handout import FavoriteHandout
from app.models.recent_search import RecentSearch
from app.models.search_keyword import SearchKeyword
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity
from app.models.weekly_update_content_snapshot import WeeklyUpdateContentSnapshot
from app.models.weekly_update_subscription import WeeklyUpdateSubscription

LOGGER = logging.getLogger(__name__)


def ensure_user_status_column() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "status" in columns:
        return

    LOGGER.info("db migration start | table=users add_column=status")
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
        )
    LOGGER.info("db migration complete | table=users add_column=status")


def ensure_search_keyword_no_result_count_column() -> None:
    inspector = inspect(engine)
    if "search_keywords" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("search_keywords")}
    if "no_result_count" in columns:
        return

    LOGGER.info("db migration start | table=search_keywords add_column=no_result_count")
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE search_keywords "
                "ADD COLUMN no_result_count INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "UPDATE search_keywords SET no_result_count = 1 "
                "WHERE last_has_result = 0 OR last_result_count <= 0"
            )
        )
    LOGGER.info("db migration complete | table=search_keywords add_column=no_result_count")


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
    ensure_user_status_column()
    ensure_search_keyword_no_result_count_column()

    db = SessionLocal()
    try:
        seed_conclusions_if_empty(db)
    finally:
        db.close()
    LOGGER.info("db init complete")
