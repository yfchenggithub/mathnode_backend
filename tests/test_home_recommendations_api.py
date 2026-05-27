from __future__ import annotations

import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_index_store
from app.api.deps import get_db
from app.api.v1.search import router as search_router
from app.loaders.index_loader import load_index_records
from app.stores.memory_index_store import MemoryIndexStore


class HomeRecommendationsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        index_path = Path("app/data/backend_search_index.json")
        index_result = load_index_records(index_file_path=index_path)
        cls._index_store = MemoryIndexStore(
            records=index_result.records,
            source=index_result.source,
            generated_at=index_result.generated_at,
        )

    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(search_router, prefix="/api/v1")
        app.dependency_overrides[get_index_store] = lambda: self._index_store

        def _fake_db():
            yield None

        app.dependency_overrides[get_db] = _fake_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_home_recommendations_returns_items(self) -> None:
        response = self.client.get("/api/v1/home/recommendations?limit=5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")

        data = payload["data"]
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertIn("generated_at", data)
        self.assertIsInstance(data["items"], list)
        self.assertLessEqual(len(data["items"]), 5)

        if data["items"]:
            first = data["items"][0]
            self.assertIn("id", first)
            self.assertIn("title", first)
            self.assertIn("module", first)
            self.assertIn("category", first)
            self.assertIn("tags", first)
            self.assertIn("summary", first)
            self.assertIn("is_favorited", first)
            self.assertIsInstance(first["is_favorited"], bool)

    def test_home_recommendations_limit_validation(self) -> None:
        response = self.client.get("/api/v1/home/recommendations?limit=0")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
