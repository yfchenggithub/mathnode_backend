from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import MOCK_TOKEN, get_db
from app.api.v1.correction_reports import router as correction_reports_router
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base


class CorrectionReportApiTests(unittest.TestCase):
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
        app.include_router(correction_reports_router, prefix="/api/v1")
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

    def _create_report(self) -> dict:
        response = self.client.post(
            "/api/v1/correction-reports",
            json={
                "conclusion_id": "I033",
                "conclusion_title": "对数平均值不等式",
                "error_location": "core_formula",
                "error_type": "formula",
                "description": "中间公式少了一个括号",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        return payload["data"]

    def test_create_allows_anonymous_user(self) -> None:
        data = self._create_report()

        self.assertEqual(data["conclusion_id"], "I033")
        self.assertEqual(data["conclusion_title"], "对数平均值不等式")
        self.assertEqual(data["error_location"], "core_formula")
        self.assertEqual(data["error_type"], "formula")
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["user_id"])

    def test_create_rejects_empty_required_content(self) -> None:
        response = self.client.post(
            "/api/v1/correction-reports",
            json={
                "conclusion_id": "I033",
                "conclusion_title": "对数平均值不等式",
                "description": "   ",
            },
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], 4231)

    def test_admin_list_reports(self) -> None:
        created = self._create_report()

        list_response = self.client.get(
            "/api/v1/admin/correction-reports",
            headers=self._auth_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertEqual(list_payload["data"]["total"], 1)
        self.assertEqual(list_payload["data"]["items"][0]["id"], created["id"])

    def test_admin_list_requires_login(self) -> None:
        response = self.client.get("/api/v1/admin/correction-reports")

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 4011)


if __name__ == "__main__":
    unittest.main()
