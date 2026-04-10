"""
用途：
- 收藏业务编排层
职责：
- 收藏关系继续走 SQLite repository
- 结论存在性与元信息读取走 ContentStore（内存）
"""

from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.repositories.favorite_repo import FavoriteRepository
from app.stores.interfaces import ContentStore


class FavoriteService:
    @staticmethod
    def add_favorite(
        db: Session,
        user_id: str,
        conclusion_id: str,
        content_store: ContentStore,
    ) -> None:
        if not content_store.exists(conclusion_id):
            raise BizException(code=4040, message="结论不存在")

        if FavoriteRepository.exists(db, user_id, conclusion_id):
            return

        FavoriteRepository.create(db, user_id, conclusion_id)

    @staticmethod
    def remove_favorite(db: Session, user_id: str, conclusion_id: str) -> None:
        FavoriteRepository.delete(db, user_id, conclusion_id)

    @staticmethod
    def list_favorites(db: Session, user_id: str, content_store: ContentStore) -> dict:
        favorite_ids = FavoriteRepository.list_ids(db, user_id)
        items = []

        for conclusion_id in favorite_ids:
            summary = content_store.get_summary(conclusion_id)
            if not summary:
                continue
            items.append(
                {
                    "conclusion_id": summary["id"],
                    "title": summary["title"],
                    "module": summary["module"],
                }
            )

        items.sort(key=lambda x: x["conclusion_id"])

        return {
            "total": len(items),
            "items": items,
        }

    @staticmethod
    def get_favorite_ids(db: Session, user_id: str) -> set[str]:
        return FavoriteRepository.list_ids(db, user_id)
