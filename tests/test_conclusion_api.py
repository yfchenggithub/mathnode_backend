from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_content_store
from app.api.deps import get_db
from app.api.v1.conclusions import router as conclusions_router
from app.loaders.content_loader import load_content_from_json
from app.stores.memory_content_store import MemoryContentStore


class ConclusionApiRawRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        canonical_path = Path("app/data/canonical_content_v2.json")
        cls._canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))

        content_result = load_content_from_json(canonical_path)
        cls._content_store = MemoryContentStore(
            documents=content_result.records,
            source=content_result.source,
            raw_records_by_id=content_result.raw_records_by_id,
        )

    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(conclusions_router, prefix="/api/v1")

        app.dependency_overrides[get_content_store] = lambda: self._content_store

        def _fake_db():
            yield None

        app.dependency_overrides[get_db] = _fake_db

        self._app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    @staticmethod
    def _expected_pdf_url(raw_record: dict[str, object]) -> str | None:
        assets = raw_record.get("assets")
        if not isinstance(assets, dict):
            return None

        raw_pdf = assets.get("pdf")
        if not isinstance(raw_pdf, str):
            return None

        pdf_name = raw_pdf.strip()
        if not pdf_name:
            return None

        if pdf_name.startswith(("http://", "https://", "/")):
            return pdf_name

        return f"/api/v1/pdfs/{quote(pdf_name)}"

    def test_get_i040_returns_raw_record_plus_derived_fields(self) -> None:
        response = self.client.get("/api/v1/conclusions/I040")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)

        expected = deepcopy(self._canonical_payload["I040"])
        expected["is_favorited"] = False
        expected["pdf_url"] = self._expected_pdf_url(expected)

        self.assertEqual(payload["data"], expected)


if __name__ == "__main__":
    unittest.main()
