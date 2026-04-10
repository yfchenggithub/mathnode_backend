from sqlalchemy.orm import Session

from app.repositories.recent_search_repo import RecentSearchRepository


class RecentSearchService:
    @staticmethod
    def add_keyword(db: Session, user_id: str, keyword: str) -> None:
        RecentSearchRepository.add_keyword(db, user_id, keyword, keep_limit=10)

    @staticmethod
    def list_recent(db: Session, user_id: str, limit: int = 10) -> dict:
        rows = RecentSearchRepository.list_recent(db, user_id, limit=limit)
        return {
            "total": len(rows),
            "items": [
                {
                    "keyword": row.keyword,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
        }

    @staticmethod
    def clear_all(db: Session, user_id: str) -> None:
        RecentSearchRepository.clear_all(db, user_id)
