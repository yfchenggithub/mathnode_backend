from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.favorite_handout import FavoriteHandout


class FavoriteHandoutRepository:
    @staticmethod
    def create(
        db: Session,
        *,
        handout_id: str,
        user_id: str,
        title: str,
        status: str,
        item_count: int,
        filename: str | None,
        stored_filename: str | None,
        snapshot_conclusion_ids_json: str,
        created_at,
        expires_at,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> FavoriteHandout:
        obj = FavoriteHandout(
            handout_id=handout_id,
            user_id=user_id,
            title=title,
            status=status,
            item_count=item_count,
            filename=filename,
            stored_filename=stored_filename,
            snapshot_conclusion_ids_json=snapshot_conclusion_ids_json,
            created_at=created_at,
            expires_at=expires_at,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def get_by_handout_id_and_user_id(
        db: Session,
        *,
        handout_id: str,
        user_id: str,
    ) -> FavoriteHandout | None:
        stmt = select(FavoriteHandout).where(
            FavoriteHandout.handout_id == handout_id,
            FavoriteHandout.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()
