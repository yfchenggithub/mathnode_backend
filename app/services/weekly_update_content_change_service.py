from __future__ import annotations

import logging
import json
import threading
from collections.abc import Mapping, Sequence
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
        observed_ids: Sequence[str] | None = None,
        title_by_id: Mapping[str, str] | None = None,
        metric_name: str = "pdf_mapping_count",
    ) -> dict:
        current_count = max(0, int(observed_count or 0))
        current_ids = WeeklyUpdateContentChangeService._normalize_ids(observed_ids)
        row = db.get(WeeklyUpdateContentSnapshot, WeeklyUpdateContentChangeService.SNAPSHOT_KEY)

        if row is None:
            row = WeeklyUpdateContentSnapshot(
                key=WeeklyUpdateContentChangeService.SNAPSHOT_KEY,
                observed_count=current_count,
                observed_ids_json=WeeklyUpdateContentChangeService._encode_ids(current_ids),
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
                "new_ids": [],
            }

        previous_count = max(0, int(row.observed_count or 0))
        previous_ids = WeeklyUpdateContentChangeService._decode_ids(row.observed_ids_json)
        if current_count <= previous_count:
            row.observed_count = current_count
            row.observed_ids_json = WeeklyUpdateContentChangeService._encode_ids(current_ids)
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
                "new_ids": [],
            }

        new_ids = [conclusion_id for conclusion_id in current_ids if conclusion_id not in previous_ids]
        count_delta = current_count - previous_count
        limit = max(1, min(2000, int(settings.WECHAT_WEEKLY_UPDATE_AUTO_NOTIFY_LIMIT or 2000)))
        project_name = WeeklyUpdateContentChangeService._build_project_name(
            new_ids=new_ids,
            title_by_id=title_by_id or {},
            count_delta=count_delta,
        )
        payload = WeeklyUpdateNotificationSendRequest(
            project_name=project_name,
            project_progress="已更新",
            limit=limit,
        )
        LOGGER.info(
            (
                "weekly update content count notification trigger | request_id=%s "
                "metric=%s previous_count=%s current_count=%s new_ids=%s "
                "project_name=%r limit=%s"
            ),
            get_request_id(),
            metric_name,
            previous_count,
            current_count,
            new_ids[:10],
            project_name,
            limit,
        )

        result = WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers(
            db=db,
            payload=payload,
        )

        now = datetime.utcnow()
        row.observed_count = current_count
        row.observed_ids_json = WeeklyUpdateContentChangeService._encode_ids(current_ids)
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
            "new_ids": new_ids,
            **result,
        }

    @staticmethod
    def run_count_check(
        *,
        observed_count: int,
        observed_ids: Sequence[str] | None = None,
        title_by_id: Mapping[str, str] | None = None,
        metric_name: str = "pdf_mapping_count",
    ) -> None:
        db = SessionLocal()
        try:
            WeeklyUpdateContentChangeService.check_count_and_notify(
                db=db,
                observed_count=observed_count,
                observed_ids=observed_ids,
                title_by_id=title_by_id,
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
        observed_ids: Sequence[str] | None = None,
        title_by_id: Mapping[str, str] | None = None,
        metric_name: str = "pdf_mapping_count",
    ) -> None:
        thread = threading.Thread(
            target=WeeklyUpdateContentChangeService.run_count_check,
            kwargs={
                "observed_count": observed_count,
                "observed_ids": list(observed_ids or []),
                "title_by_id": dict(title_by_id or {}),
                "metric_name": metric_name,
            },
            name="weekly-update-count-check",
            daemon=True,
        )
        thread.start()

    @staticmethod
    def _normalize_ids(values: Sequence[str] | None) -> list[str]:
        if not values:
            return []

        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            conclusion_id = str(value or "").strip()
            if not conclusion_id or conclusion_id in seen:
                continue
            seen.add(conclusion_id)
            result.append(conclusion_id)
        return sorted(result)

    @staticmethod
    def _encode_ids(values: Sequence[str]) -> str:
        return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_ids(raw_value: str | None) -> set[str]:
        try:
            parsed = json.loads(raw_value or "[]")
        except json.JSONDecodeError:
            return set()

        if not isinstance(parsed, list):
            return set()
        return {
            str(value or "").strip()
            for value in parsed
            if str(value or "").strip()
        }

    @staticmethod
    def _fit_thing_value(value: str) -> str:
        text = str(value or "").strip()
        if len(text) <= 20:
            return text
        return text[:20]

    @staticmethod
    def _build_project_name(
        *,
        new_ids: Sequence[str],
        title_by_id: Mapping[str, str],
        count_delta: int,
    ) -> str:
        safe_delta = max(1, int(count_delta or 1))
        if not new_ids:
            return WeeklyUpdateContentChangeService._fit_thing_value(
                f"新增{safe_delta}条二级结论"
            )

        first_id = new_ids[0]
        first_title = str(title_by_id.get(first_id) or first_id or "").strip()
        if not first_title:
            first_title = f"新增{safe_delta}条二级结论"

        if safe_delta <= 1:
            return WeeklyUpdateContentChangeService._fit_thing_value(first_title)

        suffix = f"等{safe_delta}条"
        max_title_length = max(1, 20 - len(suffix))
        return f"{first_title[:max_title_length]}{suffix}"
