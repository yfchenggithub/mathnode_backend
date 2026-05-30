from __future__ import annotations

import json
import shutil
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pikepdf
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_content_store, get_pdf_mapping_store
from app.api.deps import MOCK_TOKEN, get_db
from app.api.v1.favorites import router as favorites_router
from app.api.v1.pdfs import router as pdf_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.db.base import Base
from app.models.favorite import Favorite
from app.models.favorite_handout import FavoriteHandout
from app.services.auth_service import AuthService
from app.stores.memory_pdf_mapping_store import MemoryPdfMappingStore


class _FakeContentStore:
    def __init__(self, summaries: dict[str, str]) -> None:
        self._summaries = summaries

    def get_by_id(self, conclusion_id: str):
        if conclusion_id not in self._summaries:
            return None
        return {
            "id": conclusion_id,
            "title": self._summaries[conclusion_id],
            "module": "test",
            "difficulty": 1,
            "tags": [],
            "statement_clean": "",
            "statement": "",
            "explanation": "",
            "proof": "",
            "examples": [],
            "traps": [],
            "summary": "",
            "pdf_url": None,
        }

    def get_raw_by_id(self, conclusion_id: str):
        doc = self.get_by_id(conclusion_id)
        if doc is None:
            return None
        return dict(doc)

    def exists(self, conclusion_id: str) -> bool:
        return conclusion_id in self._summaries

    def get_summary(self, conclusion_id: str):
        title = self._summaries.get(conclusion_id)
        if title is None:
            return None
        return {
            "id": conclusion_id,
            "title": title,
            "module": "test",
        }

    def count(self) -> int:
        return len(self._summaries)

    def stats(self) -> dict:
        return {"count": len(self._summaries)}


class FavoriteHandoutApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = Path("tests") / ".tmp" / f"favorite_handout_{uuid.uuid4().hex}"
        self._tmp_root.mkdir(parents=True, exist_ok=True)
        self._pdf_root = self._tmp_root / "pdfs"
        self._handout_root = self._tmp_root / "handouts"
        self._pdf_root.mkdir(parents=True, exist_ok=True)
        self._handout_root.mkdir(parents=True, exist_ok=True)

        self._old_pdf_root = settings.PDF_ROOT_DIR
        self._old_handout_root = settings.HANDOUT_OUTPUT_DIR
        self._old_handout_expire_days = settings.HANDOUT_EXPIRE_DAYS
        self._old_handout_timezone = settings.HANDOUT_TIMEZONE

        settings.PDF_ROOT_DIR = str(self._pdf_root)
        settings.HANDOUT_OUTPUT_DIR = str(self._handout_root)
        settings.HANDOUT_EXPIRE_DAYS = 7
        settings.HANDOUT_TIMEZONE = "Asia/Shanghai"

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

        self._content_store = _FakeContentStore(
            summaries={
                "I001": "标题 I001",
                "I002": "标题 I002",
                "I040": "标题 I040",
            }
        )
        self._pdf_mapping_store = MemoryPdfMappingStore(
            mapping={
                "I001": "I001.pdf",
                "I002": "I002.pdf",
                "I040": "I040.pdf",
            },
            source="unit-test",
        )

        self._write_pdf(self._pdf_root / "I001.pdf", widths=[200])
        self._write_pdf(self._pdf_root / "I002.pdf", widths=[320, 320])
        self._write_pdf(self._pdf_root / "I040.pdf", widths=[280])

        app = FastAPI()
        app.include_router(favorites_router, prefix="/api/v1")
        app.include_router(pdf_router, prefix="/api/v1")
        register_exception_handlers(app)

        def _override_db():
            db = self._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_content_store] = lambda: self._content_store
        app.dependency_overrides[get_pdf_mapping_store] = lambda: self._pdf_mapping_store

        self.client = TestClient(app)
        self._auth_headers = {"Authorization": f"Bearer {MOCK_TOKEN}"}
        self._auth_headers_user2 = {
            "Authorization": f"Bearer {AuthService.create_access_token('u2002')}"
        }

    def tearDown(self) -> None:
        self.client.close()
        self._engine.dispose()
        settings.PDF_ROOT_DIR = self._old_pdf_root
        settings.HANDOUT_OUTPUT_DIR = self._old_handout_root
        settings.HANDOUT_EXPIRE_DAYS = self._old_handout_expire_days
        settings.HANDOUT_TIMEZONE = self._old_handout_timezone
        if self._tmp_root.exists():
            shutil.rmtree(self._tmp_root, ignore_errors=True)

    @staticmethod
    def _write_pdf(path: Path, widths: list[int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = pikepdf.Pdf.new()
        for width in widths:
            writer.add_blank_page(page_size=(float(width), 200.0))
        writer.save(str(path))
        writer.close()

    def _insert_favorite(self, *, user_id: str, conclusion_id: str) -> None:
        db: Session = self._session_factory()
        try:
            db.add(Favorite(user_id=user_id, conclusion_id=conclusion_id))
            db.commit()
        finally:
            db.close()

    def _find_handout(self) -> FavoriteHandout:
        db: Session = self._session_factory()
        try:
            stmt = select(FavoriteHandout).limit(1)
            handout = db.execute(stmt).scalar_one()
            db.expunge(handout)
            return handout
        finally:
            db.close()

    def _find_handout_by_public_id(self, handout_id: str) -> FavoriteHandout:
        db: Session = self._session_factory()
        try:
            stmt = select(FavoriteHandout).where(FavoriteHandout.handout_id == handout_id)
            handout = db.execute(stmt).scalar_one()
            db.expunge(handout)
            return handout
        finally:
            db.close()

    def test_post_requires_auth(self) -> None:
        response = self.client.post("/api/v1/favorites/handouts")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 4011)

    def test_post_rejects_client_controlled_fields(self) -> None:
        response = self.client.post(
            "/api/v1/favorites/handouts",
            headers=self._auth_headers,
            json={"conclusion_ids": ["I001"]},
        )
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["code"], 4220)

    def test_post_no_favorites_returns_no_favorites(self) -> None:
        response = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error_code"], "NO_FAVORITES")
        self.assertEqual(payload["message"], "当前没有可生成讲义的收藏内容")

    def test_post_merges_pdfs_in_favorite_default_order(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I002")
        self._insert_favorite(user_id="u1001", conclusion_id="I001")

        response = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        self.assertEqual(response.status_code, 201)

        payload = response.json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["item_count"], 2)
        self.assertTrue(data["pdf_url"].startswith("/api/v1/favorites/handouts/"))

        handout = self._find_handout_by_public_id(data["handout_id"])
        merged_path = self._handout_root / str(handout.stored_filename)
        self.assertTrue(merged_path.exists())

        reader = pikepdf.Pdf.open(str(merged_path))
        self.assertEqual(len(reader.pages), 3)
        first_page_width = float(reader.pages[0].MediaBox[2])
        second_page_width = float(reader.pages[1].MediaBox[2])
        self.assertEqual(first_page_width, 200.0)
        self.assertEqual(second_page_width, 320.0)
        reader.close()

    def test_post_missing_source_pdf_fails_whole_generation(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        self._insert_favorite(user_id="u1001", conclusion_id="I040")
        self._pdf_mapping_store = MemoryPdfMappingStore(
            mapping={
                "I001": "I001.pdf",
            },
            source="unit-test-missing",
        )

        response = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error_code"], "HANDOUT_SOURCE_PDF_MISSING")
        self.assertIn("missing_items", payload)
        self.assertEqual(payload["missing_items"][0]["conclusion_id"], "I040")

        serialized_payload = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(str(self._pdf_root.resolve()), serialized_payload)

        db: Session = self._session_factory()
        try:
            total = db.execute(select(FavoriteHandout)).scalars().all()
            self.assertEqual(len(total), 0)
        finally:
            db.close()

    def test_get_handout_only_owner_can_query(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}",
            headers=self._auth_headers_user2,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "HANDOUT_NOT_FOUND")

    def test_get_pdf_only_owner_can_download(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}/pdf",
            headers=self._auth_headers_user2,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "HANDOUT_NOT_FOUND")

    def test_guessing_other_handout_id_returns_404(self) -> None:
        guessed_id = f"fh_{uuid.uuid4().hex}"
        response = self.client.get(
            f"/api/v1/favorites/handouts/{guessed_id}",
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "HANDOUT_NOT_FOUND")

    def test_expired_handout_cannot_be_downloaded(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        db: Session = self._session_factory()
        try:
            stmt = select(FavoriteHandout).where(FavoriteHandout.handout_id == handout_id)
            handout = db.execute(stmt).scalar_one()
            handout.expires_at = datetime.utcnow() - timedelta(days=1)
            db.commit()
        finally:
            db.close()

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}/pdf",
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertEqual(payload["error_code"], "HANDOUT_EXPIRED")

    def test_expired_handout_metadata_returns_status_expired(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        db: Session = self._session_factory()
        try:
            stmt = select(FavoriteHandout).where(FavoriteHandout.handout_id == handout_id)
            handout = db.execute(stmt).scalar_one()
            handout.expires_at = datetime.utcnow() - timedelta(days=1)
            db.commit()
        finally:
            db.close()

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}",
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["status"], "expired")

    def test_metadata_exists_but_file_missing_returns_500(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        db: Session = self._session_factory()
        try:
            stmt = select(FavoriteHandout).where(FavoriteHandout.handout_id == handout_id)
            handout = db.execute(stmt).scalar_one()
            handout.stored_filename = "missing_after_create.pdf"
            db.commit()
        finally:
            db.close()

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}/pdf",
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["error_code"], "HANDOUT_FILE_MISSING")

    def test_pdf_download_uses_inline_and_utf8_filename(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I001")
        create_resp = self.client.post("/api/v1/favorites/handouts", headers=self._auth_headers)
        handout_id = create_resp.json()["data"]["handout_id"]

        response = self.client.get(
            f"/api/v1/favorites/handouts/{handout_id}/pdf",
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        content_disposition = response.headers.get("content-disposition", "")
        self.assertIn("inline", content_disposition)
        self.assertIn("filename*=", content_disposition)
        self.assertIn(quote("收藏讲义"), content_disposition)

    def test_original_favorites_list_endpoint_still_works(self) -> None:
        self._insert_favorite(user_id="u1001", conclusion_id="I002")
        self._insert_favorite(user_id="u1001", conclusion_id="I001")

        response = self.client.get("/api/v1/favorites", headers=self._auth_headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        items = payload["data"]["items"]
        self.assertEqual([item["conclusion_id"] for item in items], ["I001", "I002"])

    def test_original_single_pdf_endpoint_still_works(self) -> None:
        response = self.client.get("/api/v1/pdfs/I001.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")

    def test_openapi_contains_three_new_endpoints(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("/api/v1/favorites/handouts", paths)
        self.assertIn("/api/v1/favorites/handouts/{handout_id}", paths)
        self.assertIn("/api/v1/favorites/handouts/{handout_id}/pdf", paths)


if __name__ == "__main__":
    unittest.main()
