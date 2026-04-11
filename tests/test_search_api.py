from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_index_store
from app.api.deps import get_db
from app.api.v1.search import router as search_router
from app.loaders.index_loader import load_index_records
from app.stores.memory_index_store import MemoryIndexStore


class SearchApiIndexPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        index_path = Path("app/data/backend_search_index.json")
        index_json = json.loads(index_path.read_text(encoding="utf-8"))
        cls._docs = index_json["docs"]

        index_result = load_index_records(index_file_path=index_path)
        cls._index_store = MemoryIndexStore(
            records=index_result.records,
            source=index_result.source,
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

    def test_search_item_i001_matches_index_docs_plus_is_favorited(self) -> None:
        keyword = "\u4e0d\u7b49\u5f0f"
        response = self.client.get(f"/api/v1/search?q={keyword}&page_size=50")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)

        items = payload["data"]["items"]
        i001_item = next((item for item in items if item.get("id") == "I001"), None)
        self.assertIsNotNone(i001_item, "Expected I001 in /search response")

        assert i001_item is not None
        self.assertIn("is_favorited", i001_item)
        self.assertIsInstance(i001_item["is_favorited"], bool)
        self.assertFalse(i001_item["is_favorited"])

        expected = deepcopy(self._docs["I001"])
        actual = deepcopy(i001_item)
        actual.pop("is_favorited", None)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
