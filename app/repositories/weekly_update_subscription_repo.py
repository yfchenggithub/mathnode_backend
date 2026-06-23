from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.weekly_update_subscription import WeeklyUpdateSubscription


class WeeklyUpdateSubscriptionRepository:
    @staticmethod
    def get_by_user_and_template(
        db: Session,
        *,
        user_id: str,
        template_id: str,
    ) -> WeeklyUpdateSubscription | None:
        stmt = select(WeeklyUpdateSubscription).where(
            WeeklyUpdateSubscription.user_id == user_id,
            WeeklyUpdateSubscription.template_id == template_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_or_create_by_user_and_template(
        db: Session,
        *,
        user_id: str,
        template_id: str,
    ) -> WeeklyUpdateSubscription:
        record = WeeklyUpdateSubscriptionRepository.get_by_user_and_template(
            db=db,
            user_id=user_id,
            template_id=template_id,
        )
        if record is not None:
            return record

        record = WeeklyUpdateSubscription(
            user_id=user_id,
            template_id=template_id,
            status=WeeklyUpdateSubscription.STATUS_INACTIVE,
            available_count=0,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def list_send_candidates(
        db: Session,
        *,
        template_id: str,
        limit: int,
    ) -> list[WeeklyUpdateSubscription]:
        stmt = (
            select(WeeklyUpdateSubscription)
            .where(
                WeeklyUpdateSubscription.template_id == template_id,
                WeeklyUpdateSubscription.status == WeeklyUpdateSubscription.STATUS_ACTIVE,
                WeeklyUpdateSubscription.available_count > 0,
            )
            .order_by(
                desc(WeeklyUpdateSubscription.available_count),
                WeeklyUpdateSubscription.id,
            )
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def apply_authorization_result(
        db: Session,
        *,
        record: WeeklyUpdateSubscription,
        result: str,
        prompt_source: str | None,
    ) -> WeeklyUpdateSubscription:
        now = datetime.utcnow()
        record.last_request_result = result
        record.last_prompt_source = prompt_source
        record.updated_at = now

        if result == "accept":
            record.status = WeeklyUpdateSubscription.STATUS_ACTIVE
            record.available_count = max(0, int(record.available_count or 0)) + 1
            record.total_accept_count = int(record.total_accept_count or 0) + 1
            record.last_authorized_at = now
        else:
            record.total_reject_count = int(record.total_reject_count or 0) + 1
            if record.total_accept_count <= 0:
                record.status = WeeklyUpdateSubscription.STATUS_INACTIVE

        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def consume_one_send(
        db: Session,
        *,
        record: WeeklyUpdateSubscription,
    ) -> WeeklyUpdateSubscription:
        record.available_count = max(0, int(record.available_count or 0) - 1)
        record.total_sent_count = int(record.total_sent_count or 0) + 1
        record.last_sent_at = datetime.utcnow()
        record.updated_at = record.last_sent_at
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def deactivate(
        db: Session,
        *,
        record: WeeklyUpdateSubscription,
    ) -> WeeklyUpdateSubscription:
        record.status = WeeklyUpdateSubscription.STATUS_INACTIVE
        record.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(record)
        return record
