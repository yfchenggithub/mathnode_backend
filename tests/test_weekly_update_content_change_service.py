from __future__ import annotations

import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.models.weekly_update_content_snapshot import WeeklyUpdateContentSnapshot
from app.services.weekly_update_content_change_service import (
    WeeklyUpdateContentChangeService,
)


class WeeklyUpdateContentChangeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_limit = settings.WECHAT_WEEKLY_UPDATE_AUTO_NOTIFY_LIMIT
        settings.WECHAT_WEEKLY_UPDATE_AUTO_NOTIFY_LIMIT = 2000

        self._engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
        )
        Base.metadata.create_all(bind=self._engine)
        self.db = self._session_factory()

    def tearDown(self) -> None:
        self.db.close()
        self._engine.dispose()
        settings.WECHAT_WEEKLY_UPDATE_AUTO_NOTIFY_LIMIT = self._old_limit

    def _snapshot(self) -> WeeklyUpdateContentSnapshot | None:
        return self.db.get(
            WeeklyUpdateContentSnapshot,
            WeeklyUpdateContentChangeService.SNAPSHOT_KEY,
        )

    def _insert_snapshot(self, observed_count: int, observed_ids_json: str = "[]") -> None:
        self.db.add(
            WeeklyUpdateContentSnapshot(
                key=WeeklyUpdateContentChangeService.SNAPSHOT_KEY,
                observed_count=observed_count,
                observed_ids_json=observed_ids_json,
            )
        )
        self.db.commit()

    def test_first_count_creates_baseline_without_notification(self) -> None:
        with mock.patch(
            (
                "app.services.weekly_update_content_change_service."
                "WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers"
            )
        ) as mocked_send:
            result = WeeklyUpdateContentChangeService.check_count_and_notify(
                db=self.db,
                observed_count=12,
                observed_ids=["A", "B"],
            )

        self.assertFalse(result["triggered"])
        self.assertEqual(result["reason"], "baseline_created")
        self.assertEqual(result["current_count"], 12)
        self.assertEqual(self._snapshot().observed_count, 12)
        self.assertEqual(self._snapshot().observed_ids_json, "[\"A\",\"B\"]")
        mocked_send.assert_not_called()

    def test_count_not_increased_skips_notification_and_updates_baseline(self) -> None:
        self._insert_snapshot(12, "[\"A\",\"B\"]")

        with mock.patch(
            (
                "app.services.weekly_update_content_change_service."
                "WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers"
            )
        ) as mocked_send:
            result = WeeklyUpdateContentChangeService.check_count_and_notify(
                db=self.db,
                observed_count=10,
                observed_ids=["A"],
            )

        self.assertFalse(result["triggered"])
        self.assertEqual(result["reason"], "not_increased")
        self.assertEqual(result["previous_count"], 12)
        self.assertEqual(result["current_count"], 10)
        self.assertEqual(self._snapshot().observed_count, 10)
        self.assertEqual(self._snapshot().observed_ids_json, "[\"A\"]")
        mocked_send.assert_not_called()

    def test_count_increase_sends_notification_and_updates_baseline(self) -> None:
        self._insert_snapshot(2, "[\"A\",\"B\"]")

        with mock.patch(
            (
                "app.services.weekly_update_content_change_service."
                "WeeklyUpdateSubscriptionService.send_weekly_update_to_subscribers"
            ),
            return_value={
                "template_id": "tpl-weekly-test",
                "candidate_count": 3,
                "sent_count": 2,
                "failed_count": 1,
                "skipped_missing_openid_count": 0,
                "failures": [],
            },
        ) as mocked_send:
            result = WeeklyUpdateContentChangeService.check_count_and_notify(
                db=self.db,
                observed_count=3,
                observed_ids=["A", "B", "C"],
                title_by_id={
                    "C": "对数平均值不等式",
                },
            )

        self.assertTrue(result["triggered"])
        self.assertTrue(result["success"])
        self.assertEqual(result["previous_count"], 2)
        self.assertEqual(result["current_count"], 3)
        self.assertEqual(result["new_ids"], ["C"])
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(self._snapshot().observed_count, 3)
        self.assertEqual(self._snapshot().observed_ids_json, "[\"A\",\"B\",\"C\"]")
        self.assertIsNotNone(self._snapshot().last_notified_at)

        mocked_send.assert_called_once()
        _, kwargs = mocked_send.call_args
        self.assertEqual(kwargs["db"], self.db)
        payload = kwargs["payload"]
        self.assertEqual(payload.project_name, "对数平均值不等式")
        self.assertEqual(payload.project_progress, "已更新")
        self.assertEqual(payload.limit, 2000)


if __name__ == "__main__":
    unittest.main()
