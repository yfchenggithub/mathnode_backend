from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_content_store, get_pdf_mapping_store
from app.api.deps import get_db
from app.api.v1.conclusions import router as conclusions_router
from app.loaders.content_loader import load_content_from_json
from app.stores.memory_content_store import MemoryContentStore
from app.stores.memory_pdf_mapping_store import MemoryPdfMappingStore


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
        cls._pdf_mapping_store = MemoryPdfMappingStore(
            mapping={"I040": "demo.pdf"},
            source="test-fixture",
        )

    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(conclusions_router, prefix="/api/v1")

        app.dependency_overrides[get_content_store] = lambda: self._content_store
        app.dependency_overrides[get_pdf_mapping_store] = lambda: self._pdf_mapping_store

        def _fake_db():
            yield None

        app.dependency_overrides[get_db] = _fake_db

        self._app = app
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    @staticmethod
    def _expected_pdf_meta(conclusion_id: str) -> dict[str, str | bool | None]:
        pdf_filename = ConclusionApiRawRecordTests._pdf_mapping_store.get_pdf_filename(
            conclusion_id
        )
        if not pdf_filename:
            return {
                "pdf_url": None,
                "pdf_filename": None,
                "pdf_available": False,
            }

        return {
            "pdf_url": f"/api/v1/pdfs/{quote(pdf_filename)}",
            "pdf_filename": pdf_filename,
            "pdf_available": True,
        }

    def test_get_i040_returns_raw_record_plus_derived_fields(self) -> None:
        response = self.client.get("/api/v1/conclusions/I040")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)

        expected = deepcopy(self._canonical_payload["I040"])
        expected["is_favorited"] = False
        expected.update(self._expected_pdf_meta("I040"))

        self.assertEqual(payload["data"], expected)

    def test_get_i041_returns_no_pdf(self) -> None:
        response = self.client.get("/api/v1/conclusions/I041")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)

        expected = deepcopy(self._canonical_payload["I041"])
        expected["is_favorited"] = False
        expected.update(self._expected_pdf_meta("I041"))

        self.assertEqual(payload["data"], expected)


if __name__ == "__main__":
    unittest.main()
