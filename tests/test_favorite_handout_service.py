from __future__ import annotations

import shutil
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest import mock

import pikepdf

from app.core.config import settings
from app.core.exceptions import BizException
from app.services.favorite_handout_service import (
    FavoriteHandoutService,
    SourcePdfEntry,
    TocEntry,
)


class FavoriteHandoutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = Path("tests") / ".tmp" / f"favorite_handout_service_{uuid.uuid4().hex}"
        self._tmp_root.mkdir(parents=True, exist_ok=True)
        self._pdf_root = self._tmp_root / "pdfs"
        self._pdf_root.mkdir(parents=True, exist_ok=True)

        self._old_font_path = settings.HANDOUT_CJK_FONT_PATH
        self._old_footer_font_size = settings.HANDOUT_FOOTER_FONT_SIZE
        self._old_footer_y = settings.HANDOUT_FOOTER_Y_MM
        self._old_toc_iterations = settings.HANDOUT_TOC_MAX_ITERATIONS

        settings.HANDOUT_FOOTER_FONT_SIZE = 9
        settings.HANDOUT_FOOTER_Y_MM = 8
        settings.HANDOUT_TOC_MAX_ITERATIONS = 3

        self._font_path = self._pick_font_path()
        settings.HANDOUT_CJK_FONT_PATH = str(self._font_path) if self._font_path else ""

    def tearDown(self) -> None:
        settings.HANDOUT_CJK_FONT_PATH = self._old_font_path
        settings.HANDOUT_FOOTER_FONT_SIZE = self._old_footer_font_size
        settings.HANDOUT_FOOTER_Y_MM = self._old_footer_y
        settings.HANDOUT_TOC_MAX_ITERATIONS = self._old_toc_iterations
        if self._tmp_root.exists():
            shutil.rmtree(self._tmp_root, ignore_errors=True)

    @staticmethod
    def _pick_font_path() -> Path | None:
        candidates = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
            Path(r"C:\Windows\Fonts\simsun.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _skip_if_font_unavailable(self) -> None:
        if self._font_path is None:
            self.skipTest("No CJK font available in current test environment")

    @staticmethod
    def _write_blank_pdf(path: Path, *, page_count: int, width: float = 240.0, height: float = 180.0) -> None:
        writer = pikepdf.Pdf.new()
        for _ in range(page_count):
            writer.add_blank_page(page_size=(width, height))
        writer.save(str(path))
        writer.close()

    def test_calculate_toc_entries_start_pages_one_toc_page(self) -> None:
        entries = [
            SourcePdfEntry(order=1, conclusion_id="A", title="A", source_pdf_path=Path("a.pdf"), source_page_count=3),
            SourcePdfEntry(order=2, conclusion_id="B", title="B", source_pdf_path=Path("b.pdf"), source_page_count=2),
            SourcePdfEntry(order=3, conclusion_id="C", title="C", source_pdf_path=Path("c.pdf"), source_page_count=5),
        ]

        toc_entries = FavoriteHandoutService._calculate_toc_entries_with_start_pages(entries, toc_page_count=1)
        self.assertEqual([item.start_page for item in toc_entries], [2, 5, 7])

    def test_calculate_toc_entries_start_pages_two_toc_pages(self) -> None:
        entries = [
            SourcePdfEntry(order=1, conclusion_id="A", title="A", source_pdf_path=Path("a.pdf"), source_page_count=3),
            SourcePdfEntry(order=2, conclusion_id="B", title="B", source_pdf_path=Path("b.pdf"), source_page_count=2),
            SourcePdfEntry(order=3, conclusion_id="C", title="C", source_pdf_path=Path("c.pdf"), source_page_count=5),
        ]

        toc_entries = FavoriteHandoutService._calculate_toc_entries_with_start_pages(entries, toc_page_count=2)
        self.assertEqual([item.start_page for item in toc_entries], [3, 6, 8])

    def test_build_final_toc_pdf_until_stable_recalculates_start_page(self) -> None:
        entries = [
            SourcePdfEntry(order=1, conclusion_id="A", title="标题A", source_pdf_path=Path("a.pdf"), source_page_count=3),
            SourcePdfEntry(order=2, conclusion_id="B", title="标题B", source_pdf_path=Path("b.pdf"), source_page_count=2),
            SourcePdfEntry(order=3, conclusion_id="C", title="标题C", source_pdf_path=Path("c.pdf"), source_page_count=5),
        ]
        calls: list[list[int]] = []

        def _fake_render(
            *,
            entries_with_pages: list[TocEntry],
            item_count: int,
            total_pages: int,
            created_at: datetime,
            output_path: Path,
        ) -> int:
            del item_count, total_pages, created_at
            calls.append([entry.start_page for entry in entries_with_pages])
            rendered_pages = 2
            self._write_blank_pdf(output_path, page_count=rendered_pages, width=595.2, height=842.0)
            return rendered_pages

        with mock.patch.object(FavoriteHandoutService, "_render_toc_pdf", side_effect=_fake_render):
            result = FavoriteHandoutService._build_final_toc_pdf_until_stable(
                source_entries=entries,
                created_at=datetime.utcnow(),
                temp_dir=self._tmp_root,
            )

        self.assertEqual(calls[0], [2, 5, 7])
        self.assertEqual(calls[1], [3, 6, 8])
        self.assertEqual(result.toc_page_count, 2)
        self.assertEqual([item.start_page for item in result.toc_entries], [3, 6, 8])
        self.assertTrue(result.toc_pdf_path.exists())

    def test_render_toc_pdf_supports_multi_page(self) -> None:
        self._skip_if_font_unavailable()

        entries = [
            TocEntry(order=index, title=f"第{index}条目录测试标题" * 3, start_page=index + 1)
            for index in range(1, 80)
        ]
        output_path = self._tmp_root / "toc_multi.pdf"
        page_count = FavoriteHandoutService._render_toc_pdf(
            entries_with_pages=entries,
            item_count=len(entries),
            total_pages=120,
            created_at=datetime.utcnow(),
            output_path=output_path,
        )

        self.assertTrue(output_path.exists())
        self.assertGreater(page_count, 1)

    def test_apply_unified_page_numbers_calls_overlay_per_page(self) -> None:
        self._skip_if_font_unavailable()

        input_path = self._tmp_root / "input.pdf"
        output_path = self._tmp_root / "output.pdf"
        self._write_blank_pdf(input_path, page_count=4, width=300.0, height=200.0)

        with mock.patch.object(
            FavoriteHandoutService,
            "_render_page_number_overlay",
            wraps=FavoriteHandoutService._render_page_number_overlay,
        ) as overlay_mock:
            FavoriteHandoutService._apply_unified_page_numbers(
                input_pdf_path=input_path,
                final_output_path=output_path,
                temp_dir=self._tmp_root,
            )

        self.assertEqual(overlay_mock.call_count, 4)
        with pikepdf.Pdf.open(str(output_path)) as pdf:
            self.assertEqual(len(pdf.pages), 4)

    def test_font_unavailable_raises_business_error(self) -> None:
        settings.HANDOUT_CJK_FONT_PATH = str(self._tmp_root / "missing_font.ttf")

        with self.assertRaises(BizException) as ctx:
            FavoriteHandoutService._ensure_cjk_font_path()

        exc = ctx.exception
        self.assertEqual(exc.code, 5201)
        self.assertEqual(exc.extra.get("error_code"), "HANDOUT_FONT_UNAVAILABLE")

    def test_validate_output_pdf_detects_wrong_page_count(self) -> None:
        output_path = self._tmp_root / "invalid.pdf"
        self._write_blank_pdf(output_path, page_count=2)

        with self.assertRaises(BizException) as ctx:
            FavoriteHandoutService._validate_output_pdf(
                output_pdf_path=output_path,
                expected_total_pages=3,
            )

        exc = ctx.exception
        self.assertEqual(exc.code, 5204)
        self.assertEqual(exc.extra.get("error_code"), "HANDOUT_OUTPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
