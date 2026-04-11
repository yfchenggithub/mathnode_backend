"""
文件作用：
- 校验 PDF 接口在 MVP 场景下的核心行为与安全边界。

1.自动化测试：
python -m unittest tests.test_pdf_api -v

设计思路：
- 通过 FastAPI TestClient 挂载真实路由，验证 HTTP 层行为（状态码、响应头、JSON 错误）。
- 每个用例使用临时目录作为 PDF_ROOT_DIR，避免污染项目数据目录。

主要功能：
- 覆盖 inline 预览、attachment 下载、404 文件不存在、400 路径穿越拦截。

为什么这样设计：
- 用最小成本提供可重复、可自动化的回归验证，保障后续改动不破坏 PDF 接口约定。
"""

from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.pdfs import router as pdf_router
from app.core.config import settings


class PdfApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_pdf_root_dir = settings.PDF_ROOT_DIR
        self._tmp_root = Path("tests") / ".tmp" / f"pdfs_{uuid.uuid4().hex}"
        self._tmp_root.mkdir(parents=True, exist_ok=True)

        settings.PDF_ROOT_DIR = str(self._tmp_root)

        self._write_pdf(self._tmp_root / "demo.pdf")
        self._write_pdf(self._tmp_root / "演示.pdf")

        app = FastAPI()
        app.include_router(pdf_router, prefix="/api/v1")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        settings.PDF_ROOT_DIR = self._old_pdf_root_dir
        if self._tmp_root.exists():
            shutil.rmtree(self._tmp_root, ignore_errors=True)

    @staticmethod
    def _write_pdf(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
            b"trailer << /Root 1 0 R >>\n%%EOF"
        )

    def test_preview_pdf_inline(self) -> None:
        response = self.client.get("/api/v1/pdfs/demo.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")
        self.assertIn("inline", response.headers.get("content-disposition", ""))

    def test_download_pdf_attachment_and_chinese_filename(self) -> None:
        path = quote("演示.pdf")
        response = self.client.get(f"/api/v1/pdfs/{path}?download=1")
        self.assertEqual(response.status_code, 200)
        content_disposition = response.headers.get("content-disposition", "")
        self.assertIn("attachment", content_disposition)
        self.assertIn("filename*=", content_disposition)

    def test_file_not_found_returns_404_json(self) -> None:
        response = self.client.get("/api/v1/pdfs/not-exists.pdf")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["code"], 4040)
        self.assertEqual(payload["message"], "PDF 文件不存在")
        self.assertIsNone(payload["data"])

    def test_path_traversal_returns_400_json(self) -> None:
        response = self.client.get("/api/v1/pdfs/%2E%2E/secret.pdf")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 4001)
        self.assertEqual(payload["message"], "文件路径不合法")
        self.assertIsNone(payload["data"])


if __name__ == "__main__":
    unittest.main()
