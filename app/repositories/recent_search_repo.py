from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.recent_search import RecentSearch


class RecentSearchRepository:
    @staticmethod
    def add_keyword(
        db: Session, user_id: str, keyword: str, keep_limit: int = 10
    ) -> None:
        keyword = keyword.strip()
        if not keyword:
            return

        # 先删旧记录，避免同一用户同关键词重复
        delete_stmt = delete(RecentSearch).where(
            RecentSearch.user_id == user_id,
            RecentSearch.keyword == keyword,
        )
        db.execute(delete_stmt)
        db.commit()

        obj = RecentSearch(user_id=user_id, keyword=keyword)
        db.add(obj)
        db.commit()

        # 只保留最近 keep_limit 条
        stmt = (
            select(RecentSearch)
            .where(RecentSearch.user_id == user_id)
            .order_by(desc(RecentSearch.created_at), desc(RecentSearch.id))
        )
        rows = db.execute(stmt).scalars().all()

        if len(rows) > keep_limit:
            for item in rows[keep_limit:]:
                db.delete(item)
            db.commit()

    @staticmethod
    def list_recent(db: Session, user_id: str, limit: int = 10) -> list[RecentSearch]:
        stmt = (
            select(RecentSearch)
            .where(RecentSearch.user_id == user_id)
            .order_by(desc(RecentSearch.created_at), desc(RecentSearch.id))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def clear_all(db: Session, user_id: str) -> None:
        stmt = delete(RecentSearch).where(RecentSearch.user_id == user_id)
        db.execute(stmt)
        db.commit()
