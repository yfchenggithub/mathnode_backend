from __future__ import annotations

import unittest
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_index_store
from app.api.deps import MOCK_TOKEN, get_db
from app.api.v1.search import router as search_router
from app.api.v1.search_keywords import router as search_keywords_router
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base


class FakeIndexStore:
    def search(
        self,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None,
    ) -> dict[str, Any]:
        normalized_q = q.strip().lower()
        total = 0 if normalized_q == "unknown" else 3
        return {
            "query": q,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [] if total == 0 else [{"id": "I001", "is_favorited": False}],
            "facets": {"module": [], "difficulty": [], "tags": []},
        }

    def suggest(self, q: str) -> dict[str, Any]:
        return {"query": q, "total": 0, "items": []}

    def home_recommendations(
        self,
        limit: int,
        favorite_ids: set[str] | None,
    ) -> dict[str, Any]:
        return {"total": 0, "items": []}

    def count(self) -> int:
        return 1

    def stats(self) -> dict[str, Any]:
        return {}


class SearchKeywordApiTests(unittest.TestCase):
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
        app.include_router(search_router, prefix="/api/v1")
        app.include_router(search_keywords_router, prefix="/api/v1")
        register_exception_handlers(app)

        def _override_db():
            db = self._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_index_store] = lambda: FakeIndexStore()

        self.client = TestClient(app)
        self._auth_headers = {"Authorization": f"Bearer {MOCK_TOKEN}"}

    def tearDown(self) -> None:
        self.client.close()
        self._engine.dispose()

    def test_search_records_anonymous_keyword_and_admin_lists_it(self) -> None:
        first_response = self.client.get(
            "/api/v1/search",
            params={"q": " Tan x ", "page_size": 10},
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.get(
            "/api/v1/search",
            params={"q": "tan x", "page_size": 10},
        )
        self.assertEqual(second_response.status_code, 200)

        list_response = self.client.get(
            "/api/v1/admin/search-keywords",
            headers=self._auth_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["total"], 1)

        item = payload["data"]["items"][0]
        self.assertEqual(item["keyword"], "tan x")
        self.assertEqual(item["normalized_keyword"], "tan x")
        self.assertEqual(item["search_count"], 2)
        self.assertEqual(item["last_result_count"], 3)
        self.assertTrue(item["last_has_result"])

    def test_admin_list_supports_keyword_filter_and_no_result_state(self) -> None:
        response = self.client.get(
            "/api/v1/search",
            params={"q": "unknown", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200)

        list_response = self.client.get(
            "/api/v1/admin/search-keywords",
            params={"keyword": "known"},
            headers=self._auth_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        item = list_response.json()["data"]["items"][0]
        self.assertEqual(item["keyword"], "unknown")
        self.assertEqual(item["search_count"], 1)
        self.assertEqual(item["last_result_count"], 0)
        self.assertFalse(item["last_has_result"])


if __name__ == "__main__":
    unittest.main()
