from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.request_context import get_request_id
from app.db.session import SessionLocal
from app.models.weekly_update_content_snapshot import WeeklyUpdateContentSnapshot
from app.schemas.weekly_update_subscription import WeeklyUpdateNotificationSendRequest
from app.services.weekly_update_subscription_service import WeeklyUpdateSubscriptionService

LOGGER = logging.getLogger(__name__)


class WeeklyUpdateContentChangeService:
    SNAPSHOT_KEY = "weekly_update_pdf_count"

    @staticmethod
    def check_count_and_notify(
        db: Session,
        *,
        observed_count: int,
        metric_name: str = "pdf_mapping_count",
    ) -> dict:
        current_count = max(0, int(observed_count or 0))
        row = db.get(WeeklyUpdateContentSnapshot, WeeklyUpdateContentChangeService.SNAPSHOT_KEY)

        if row is None:
            row = WeeklyUpdateContentSnapshot(
                key=WeeklyUpdateContentChangeService.SNAPSHOT_KEY,
                observed_count=current_count,
            )
            db.add(row)
            db.commit()
            LOGGER.info(
                (
                    "weekly update content count baseline created | request_id=%s "
                    "metric=%s observed_count=%s"
                ),
                get_request_id(),
                metric_name,
                current_count,
            )
            return {
                "triggered": False,
                "reason": "baseline_created",
                "metric": metric_name,
                "previous_count": None,
                "current_count": current_count,
            }

        previous_count = max(0, int(row.observed_count or 0))
        if current_count <= previous_count:
            row.observed_count = current_count
            row.updated_at = datetime.utcnow()
            db.commit()
            reason = "unchanged" if current_count == previous_count else "not_increased"
            LOGGER.info(
                (
                    "weekly update content count notification skipped | request_id=%s "
                    "metric=%s previous_count=%s current_count=%s reason=%s"
                ),
                get_request_id(),
                metric_name,
                previous_count,
                current_count,
                reason,
            )
            return {
                "triggered": False,
                "reason": reason,
                "metric": metric_name,
                "previous_count": previous_count,
                "current_count": current_count,
            }

        limit = max(1, min(2000, int(settings.WECHAT_WEEKLY_UPDATE_AUTO_NOTIFY_LIMIT or 2000)))
        payload = WeeklyUpdateNotificationSendRequest(
            project_name="二级结论更新",
            project_progress="已更新",
            limit=limit,
        )
        LOGGER.info(
            (
                "weekly update content count notification trigger | request_id=%s "
                "metric=%s previous_count=%s current_count=%s limit=%s"
            ),
            get_request_id(),
            metric_name,
            previous_count,
            current_count,
            limit,
        )

        result = WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers(
            db=db,
            payload=payload,
        )

        now = datetime.utcnow()
        row.observed_count = current_count
        row.last_notified_at = now
        row.updated_at = now
        db.commit()

        LOGGER.info(
            (
                "weekly update content count notification complete | request_id=%s "
                "metric=%s previous_count=%s current_count=%s sent_count=%s "
                "failed_count=%s candidate_count=%s"
            ),
            get_request_id(),
            metric_name,
            previous_count,
            current_count,
            result.get("sent_count"),
            result.get("failed_count"),
            result.get("candidate_count"),
        )
        return {
            "triggered": True,
            "success": True,
            "metric": metric_name,
            "previous_count": previous_count,
            "current_count": current_count,
            **result,
        }

    @staticmethod
    def run_count_check(*, observed_count: int, metric_name: str = "pdf_mapping_count") -> None:
        db = SessionLocal()
        try:
            WeeklyUpdateContentChangeService.check_count_and_notify(
                db=db,
                observed_count=observed_count,
                metric_name=metric_name,
            )
        except Exception:
            LOGGER.exception(
                (
                    "weekly update content count notification failed | request_id=%s "
                    "metric=%s observed_count=%s"
                ),
                get_request_id(),
                metric_name,
                observed_count,
            )
        finally:
            db.close()

    @staticmethod
    def schedule_count_check(
        *,
        observed_count: int,
        metric_name: str = "pdf_mapping_count",
    ) -> None:
        thread = threading.Thread(
            target=WeeklyUpdateContentChangeService.run_count_check,
            kwargs={
                "observed_count": observed_count,
                "metric_name": metric_name,
            },
            name="weekly-update-count-check",
            daemon=True,
        )
        thread.start()
