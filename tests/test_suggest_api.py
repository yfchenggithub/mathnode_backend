from __future__ import annotations

import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_index_store
from app.api.v1.suggest import router as suggest_router
from app.loaders.index_loader import load_index_records
from app.stores.memory_index_store import MemoryIndexStore


class SuggestApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        index_path = Path("app/data/backend_search_index.json")
        index_result = load_index_records(index_file_path=index_path)
        cls._index_store = MemoryIndexStore(
            records=index_result.records,
            source=index_result.source,
        )

    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(suggest_router, prefix="/api/v1")
        app.dependency_overrides[get_index_store] = lambda: self._index_store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_suggest_returns_structured_items(self) -> None:
        keyword = "\u4e0d\u7b49\u5f0f"
        response = self.client.get(f"/api/v1/suggest?q={keyword}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")

        data = payload["data"]
        self.assertEqual(data["query"], keyword)
        self.assertGreaterEqual(data["total"], 1)
        self.assertIsInstance(data["items"], list)
        self.assertGreaterEqual(len(data["items"]), 1)
        self.assertLessEqual(len(data["items"]), 8)
        self.assertEqual(data["empty_hint"], "")

        first = data["items"][0]
        self.assertIn("id", first)
        self.assertIn("title", first)
        self.assertIn("subtitle", first)
        self.assertIn("route", first)
        self.assertIn("module", first)
        self.assertIn("difficulty", first)
        self.assertIn("tags", first)
        self.assertIn("match_type", first)
        self.assertIn("match_field", first)
        self.assertIn("matched_text", first)
        self.assertIn("score", first)
        self.assertIn("badge", first)
        self.assertEqual(first["matched_text"], keyword)
        self.assertEqual(first["route"], f"/conclusions/{first['id']}")
        self.assertIn("难度", first["subtitle"])
        self.assertNotIn("inequality", first["subtitle"])

    def test_suggest_empty_query_returns_empty_hint(self) -> None:
        response = self.client.get("/api/v1/suggest?q=")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")

        data = payload["data"]
        self.assertEqual(data["query"], "")
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["empty_hint"], "\u8bf7\u8f93\u5165\u5173\u952e\u8bcd")

    def test_suggest_no_match_returns_empty_items_and_hint(self) -> None:
        keyword = "__no_such_keyword__"
        response = self.client.get(f"/api/v1/suggest?q={keyword}")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")

        data = payload["data"]
        self.assertEqual(data["query"], keyword)
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["empty_hint"], "\u6ca1\u6709\u5339\u914d\u7ed3\u679c\uff0c\u6362\u4e2a\u5173\u952e\u8bcd\u8bd5\u8bd5")


if __name__ == "__main__":
    unittest.main()
