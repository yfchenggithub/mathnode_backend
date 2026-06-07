from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_index_store
from app.api.deps import get_db
from app.api.v1.search import router as search_router
from app.loaders.index_loader import load_index_records
from app.stores.memory_index_store import MemoryIndexStore


def _build_test_record(
    conclusion_id: str,
    *,
    title: str,
    rank: int = 0,
    hot_score: int = 0,
) -> dict:
    return {
        "id": conclusion_id,
        "title": title,
        "module": "test",
        "difficulty": 1,
        "tags": [],
        "statement_clean": title,
        "doc_payload": {
            "id": conclusion_id,
            "title": title,
            "module": "test",
            "difficulty": 1,
            "tags": [],
            "summary": title,
            "rank": rank,
            "hotScore": hot_score,
        },
    }


class HomeRecommendationsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        index_path = Path("app/data/backend_search_index.json")
        index_result = load_index_records(index_file_path=index_path)
        cls._index_document_count = index_result.document_count
        cls._index_store = MemoryIndexStore(
            records=index_result.records,
            source=index_result.source,
            generated_at=index_result.generated_at,
            document_count=index_result.document_count,
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
        self.assertEqual(data["total"], self._index_document_count)
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
            self.assertEqual(first["favorite_count"], 0)
            self.assertEqual(first["view_count"], 0)

    def test_home_recommendations_limit_validation(self) -> None:
        response = self.client.get("/api/v1/home/recommendations?limit=0")
        self.assertEqual(response.status_code, 422)

    def test_home_recommendations_total_uses_index_document_count(self) -> None:
        store = MemoryIndexStore(
            records=[
                _build_test_record("ONLY", title="Only returned record"),
            ],
            generated_at="2026-06-06T20:52:17+08:00",
            document_count=140,
        )

        data = store.home_recommendations(limit=1, favorite_ids=set())

        self.assertEqual(data["total"], 140)
        self.assertEqual(data["generated_at"], "2026-06-06T20:52:17+08:00")
        self.assertEqual(len(data["items"]), 1)

    def test_home_recommendations_keep_recent_pdf_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_root = Path(tmp_dir)
            old_pdf = pdf_root / "old.pdf"
            new_pdf = pdf_root / "new.pdf"
            old_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
            new_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

            old_ts = datetime(2026, 1, 1, 8, 0).timestamp()
            new_ts = datetime(2026, 1, 2, 9, 30).timestamp()
            os.utime(old_pdf, (old_ts, old_ts))
            os.utime(new_pdf, (new_ts, new_ts))

            store = MemoryIndexStore(
                records=[
                    _build_test_record("HOT", title="Hot conclusion", rank=100, hot_score=100),
                    _build_test_record("NEW", title="New conclusion", rank=0, hot_score=0),
                    _build_test_record("MID", title="Middle conclusion", rank=50, hot_score=50),
                ],
                pdf_mapping={
                    "HOT": "old.pdf",
                    "NEW": "new.pdf",
                },
                pdf_root_dir=str(pdf_root),
            )

            data = store.home_recommendations(limit=2, favorite_ids=set())
            ids = [item["id"] for item in data["items"]]
            self.assertIn("HOT", ids)
            self.assertIn("NEW", ids)

            new_item = next(item for item in data["items"] if item["id"] == "NEW")
            self.assertIn("updated_at", new_item)
            self.assertIn("2026-01-02", new_item["updated_at"])


if __name__ == "__main__":
    unittest.main()
