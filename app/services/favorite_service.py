from sqlalchemy.orm import Session

from app.repositories.conclusion_repo import ConclusionRepository
from app.repositories.favorite_repo import FavoriteRepository
from app.core.exceptions import BizException


class FavoriteService:
    @staticmethod
    def add_favorite(db: Session, user_id: str, conclusion_id: str) -> None:
        row = ConclusionRepository.get_by_id(db, conclusion_id)
        if not row:
            raise BizException(code=4040, message="结论不存在")

        if FavoriteRepository.exists(db, user_id, conclusion_id):
            return

        FavoriteRepository.create(db, user_id, conclusion_id)

    @staticmethod
    def remove_favorite(db: Session, user_id: str, conclusion_id: str) -> None:
        FavoriteRepository.delete(db, user_id, conclusion_id)

    @staticmethod
    def list_favorites(db: Session, user_id: str) -> dict:
        favorite_ids = FavoriteRepository.list_ids(db, user_id)
        items = []

        for conclusion_id in favorite_ids:
            row = ConclusionRepository.get_by_id(db, conclusion_id)
            if not row:
                continue
            items.append(
                {
                    "conclusion_id": row.id,
                    "title": row.title,
                    "module": row.module,
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
