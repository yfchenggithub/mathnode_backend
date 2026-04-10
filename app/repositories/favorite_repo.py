from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.favorite import Favorite


class FavoriteRepository:
    @staticmethod
    def exists(db: Session, user_id: str, conclusion_id: str) -> bool:
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.conclusion_id == conclusion_id,
        )
        return db.execute(stmt).scalar_one_or_none() is not None

    @staticmethod
    def create(db: Session, user_id: str, conclusion_id: str) -> Favorite:
        obj = Favorite(user_id=user_id, conclusion_id=conclusion_id)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def delete(db: Session, user_id: str, conclusion_id: str) -> None:
        stmt = select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.conclusion_id == conclusion_id,
        )
        obj = db.execute(stmt).scalar_one_or_none()
        if obj:
            db.delete(obj)
            db.commit()

    @staticmethod
    def list_ids(db: Session, user_id: str) -> set[str]:
        stmt = select(Favorite.conclusion_id).where(Favorite.user_id == user_id)
        rows = db.execute(stmt).all()
        return {row[0] for row in rows}
