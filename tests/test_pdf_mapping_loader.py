from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from app.loaders.pdf_mapping_loader import load_pdf_mapping


class PdfMappingLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = Path("tests") / ".tmp" / f"pdf_mapping_{uuid.uuid4().hex}"
        self._tmp_root.mkdir(parents=True, exist_ok=True)
        self._pdf_root = self._tmp_root / "pdfs"
        self._pdf_root.mkdir(parents=True, exist_ok=True)
        self._mapping_path = self._tmp_root / "conclusion_pdf_map.json"

    def tearDown(self) -> None:
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

    def test_load_pdf_mapping_skips_invalid_rows_when_not_strict(self) -> None:
        self._write_pdf(self._pdf_root / "demo.pdf")

        payload = {
            "I040": "demo.pdf",
            "I041": "missing.pdf",
            "I042": "../escape.pdf",
            "I043": "readme.txt",
            "": "demo.pdf",
        }
        self._mapping_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result = load_pdf_mapping(
            mapping_json_path=self._mapping_path,
            pdf_root_dir=str(self._pdf_root),
            strict=False,
        )

        self.assertEqual(result.total_rows, 5)
        self.assertEqual(result.valid_rows, 1)
        self.assertEqual(result.invalid_row_count, 4)
        self.assertEqual(result.mapping, {"I040": "demo.pdf"})

    def test_load_pdf_mapping_raises_when_strict(self) -> None:
        self._write_pdf(self._pdf_root / "demo.pdf")

        payload = {
            "I040": "demo.pdf",
            "I041": "missing.pdf",
        }
        self._mapping_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            load_pdf_mapping(
                mapping_json_path=self._mapping_path,
                pdf_root_dir=str(self._pdf_root),
                strict=True,
            )


if __name__ == "__main__":
    unittest.main()
