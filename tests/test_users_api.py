from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.v1.users import router as users_router
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base
from app.models.user import User
from app.services.auth_service import AuthService


class UsersApiTests(unittest.TestCase):
    def setUp(self) -> None:
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

        app = FastAPI()
        app.include_router(users_router, prefix="/api/v1")
        register_exception_handlers(app)

        def _override_db():
            db = self._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db

        self.client = TestClient(app)
        self._auth_headers = self._headers_for_user("u1001")
        self._disabled_headers = self._headers_for_user("u3003")
        self._seed_users()

    def tearDown(self) -> None:
        self.client.close()
        self._engine.dispose()

    @staticmethod
    def _headers_for_user(user_id: str) -> dict[str, str]:
        token = AuthService.create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    def _seed_users(self) -> None:
        now = datetime.utcnow()
        db: Session = self._session_factory()
        try:
            db.add_all(
                [
                    User(
                        id="u1001",
                        nickname="Alice",
                        avatar_url="https://example.com/alice.png",
                        status="active",
                        created_at=now - timedelta(days=3),
                        updated_at=now - timedelta(days=2),
                        last_login_at=now - timedelta(hours=1),
                    ),
                    User(
                        id="u2002",
                        nickname="Bob",
                        avatar_url=None,
                        status="active",
                        created_at=now - timedelta(days=2),
                        updated_at=now - timedelta(days=1),
                        last_login_at=None,
                    ),
                    User(
                        id="u3003",
                        nickname="Carol",
                        avatar_url=None,
                        status="disabled",
                        created_at=now - timedelta(days=1),
                        updated_at=now,
                        last_login_at=now,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

    def test_get_me_returns_current_user(self) -> None:
        response = self.client.get("/api/v1/users/me", headers=self._auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["id"], "u1001")
        self.assertEqual(payload["data"]["user_id"], "u1001")
        self.assertEqual(payload["data"]["nickname"], "Alice")
        self.assertEqual(payload["data"]["status"], "active")

    def test_list_users_requires_login(self) -> None:
        response = self.client.get("/api/v1/users")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 4011)

    def test_list_users_supports_status_keyword_and_pagination(self) -> None:
        response = self.client.get(
            "/api/v1/users",
            headers=self._auth_headers,
            params={
                "status": "active",
                "keyword": "bo",
                "page": 1,
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 1)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], "u2002")

    def test_update_user_status_disables_and_enables_account(self) -> None:
        disable_response = self.client.put(
            "/api/v1/users/u2002/status",
            headers=self._auth_headers,
            json={"status": "disabled"},
        )

        self.assertEqual(disable_response.status_code, 200)
        disable_payload = disable_response.json()
        self.assertEqual(disable_payload["data"]["id"], "u2002")
        self.assertEqual(disable_payload["data"]["status"], "disabled")

        enable_response = self.client.put(
            "/api/v1/users/u2002/status",
            headers=self._auth_headers,
            json={"status": "active"},
        )

        self.assertEqual(enable_response.status_code, 200)
        enable_payload = enable_response.json()
        self.assertEqual(enable_payload["data"]["status"], "active")

    def test_disabled_user_cannot_access_required_endpoint(self) -> None:
        response = self.client.get("/api/v1/users/me", headers=self._disabled_headers)

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["code"], 4031)
        self.assertEqual(payload["message"], "account disabled")

    def test_update_missing_user_returns_404(self) -> None:
        response = self.client.put(
            "/api/v1/users/u404/status",
            headers=self._auth_headers,
            json={"status": "disabled"},
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["code"], 4040)


if __name__ == "__main__":
    unittest.main()
