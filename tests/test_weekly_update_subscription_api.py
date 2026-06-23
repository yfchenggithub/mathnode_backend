import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import MOCK_TOKEN, get_db
from app.api.v1.weekly_update_subscriptions import router as weekly_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base
from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity
from app.models.weekly_update_subscription import WeeklyUpdateSubscription
from app.services.auth_service import AuthService
from app.services.weekly_update_subscription_service import (
    WeeklyUpdateSubscriptionService,
)


class WeeklyUpdateSubscriptionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_template_id = settings.WECHAT_WEEKLY_UPDATE_TEMPLATE_ID
        self._old_page = settings.WECHAT_WEEKLY_UPDATE_PAGE
        settings.WECHAT_WEEKLY_UPDATE_TEMPLATE_ID = "tpl-weekly-test"
        settings.WECHAT_WEEKLY_UPDATE_PAGE = "pages/search/search"

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
        self._insert_user("u1001")
        self._insert_wechat_identity("u1001", "openid-u1001")

        app = FastAPI()
        app.include_router(weekly_router, prefix="/api/v1")
        register_exception_handlers(app)

        def _override_db():
            db = self._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)
        self._headers = {"Authorization": f"Bearer {MOCK_TOKEN}"}

    def tearDown(self) -> None:
        self.client.close()
        self._engine.dispose()
        settings.WECHAT_WEEKLY_UPDATE_TEMPLATE_ID = self._old_template_id
        settings.WECHAT_WEEKLY_UPDATE_PAGE = self._old_page

    def _insert_user(self, user_id: str) -> None:
        with self._session_factory() as db:
            db.add(User(id=user_id, nickname=f"User {user_id}"))
            db.commit()

    def _insert_wechat_identity(self, user_id: str, openid: str) -> None:
        with self._session_factory() as db:
            db.add(
                UserAuthIdentity(
                    user_id=user_id,
                    provider=AuthService.WECHAT_PROVIDER,
                    provider_user_id=openid,
                    session_key="session-key",
                )
            )
            db.commit()

    def _get_subscription(self) -> WeeklyUpdateSubscription:
        with self._session_factory() as db:
            return db.execute(select(WeeklyUpdateSubscription)).scalar_one()

    def test_get_status_defaults_to_inactive(self) -> None:
        response = self.client.get(
            "/api/v1/weekly-update-subscription",
            headers=self._headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["template_id"], "tpl-weekly-test")
        self.assertEqual(data["status"], "inactive")
        self.assertFalse(data["is_following"])
        self.assertEqual(data["available_count"], 0)
        self.assertFalse(data["needs_resubscribe"])

    def test_accept_authorization_activates_and_adds_one_available_send(self) -> None:
        response = self.client.post(
            "/api/v1/weekly-update-subscription/authorization",
            headers=self._headers,
            json={"result": "accept", "source": "favorite_success"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "active")
        self.assertTrue(data["is_following"])
        self.assertEqual(data["available_count"], 1)
        self.assertFalse(data["needs_resubscribe"])
        self.assertEqual(data["last_prompt_source"], "favorite_success")

    def test_reject_after_accept_keeps_following_but_does_not_add_count(self) -> None:
        self.client.post(
            "/api/v1/weekly-update-subscription/authorization",
            headers=self._headers,
            json={"result": "accept", "source": "favorite_success"},
        )

        response = self.client.post(
            "/api/v1/weekly-update-subscription/authorization",
            headers=self._headers,
            json={"result": "reject", "source": "weekly_page"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "active")
        self.assertTrue(data["is_following"])
        self.assertEqual(data["available_count"], 1)
        self.assertEqual(data["last_request_result"], "reject")

    def test_admin_send_consumes_one_available_send_on_success(self) -> None:
        self.client.post(
            "/api/v1/weekly-update-subscription/authorization",
            headers=self._headers,
            json={"result": "accept", "source": "favorite_success"},
        )

        with mock.patch.object(
            WeeklyUpdateSubscriptionService,
            "send_subscribe_message",
            return_value={"errcode": 0},
        ) as mocked_send:
            response = self.client.post(
                "/api/v1/admin/weekly-update-notifications/send",
                headers=self._headers,
                json={
                    "project_name": "数学结论周更",
                    "project_progress": "本周新增 8 条结论",
                    "updated_at": "2026年06月23日 20:00",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["candidate_count"], 1)
        self.assertEqual(data["sent_count"], 1)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(data["skipped_missing_openid_count"], 0)
        mocked_send.assert_called_once()

        subscription = self._get_subscription()
        self.assertEqual(subscription.available_count, 0)
        self.assertEqual(subscription.total_sent_count, 1)
