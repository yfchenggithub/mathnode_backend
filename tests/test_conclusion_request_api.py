from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import MOCK_TOKEN, get_db
from app.api.v1.conclusion_requests import router as conclusion_requests_router
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base


class ConclusionRequestApiTests(unittest.TestCase):
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
        app.include_router(conclusion_requests_router, prefix="/api/v1")
        register_exception_handlers(app)

        def _override_db():
            db = self._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db

        self.client = TestClient(app)
        self._auth_headers = {"Authorization": f"Bearer {MOCK_TOKEN}"}

    def tearDown(self) -> None:
        self.client.close()
        self._engine.dispose()

    def _create_request(self, query: str = "cauchy", note: str = "need common usage") -> dict:
        response = self.client.post(
            "/api/v1/conclusion-requests",
            json={
                "query": query,
                "note": note,
                "source": "home",
                "page": "home",
                "entry": "search_no_result",
                "result_count": 0,
                "has_result": False,
                "active_tab": "all",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        return payload["data"]

    def test_create_allows_anonymous_user(self) -> None:
        data = self._create_request()

        self.assertEqual(data["query"], "cauchy")
        self.assertEqual(data["note"], "need common usage")
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["user_id"])
        self.assertEqual(data["entry"], "search_no_result")

    def test_create_rejects_empty_content(self) -> None:
        response = self.client.post(
            "/api/v1/conclusion-requests",
            json={
                "query": "   ",
                "note": "",
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], 4221)

    def test_admin_list_and_update_status(self) -> None:
        created = self._create_request(query="derivative zero", note="need hidden root")

        list_response = self.client.get(
            "/api/v1/admin/conclusion-requests",
            headers=self._auth_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertEqual(list_payload["data"]["total"], 1)
        self.assertEqual(list_payload["data"]["items"][0]["id"], created["id"])

        update_response = self.client.put(
            f"/api/v1/admin/conclusion-requests/{created['id']}",
            headers=self._auth_headers,
            json={
                "status": "updated",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.json()
        self.assertEqual(update_payload["data"]["status"], "updated")

    def test_admin_list_requires_login(self) -> None:
        response = self.client.get("/api/v1/admin/conclusion-requests")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 4011)


if __name__ == "__main__":
    unittest.main()
