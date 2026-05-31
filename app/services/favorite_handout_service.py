from __future__ import annotations

import json
import logging
import secrets
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.models.favorite_handout import FavoriteHandout
from app.repositories.favorite_handout_repo import FavoriteHandoutRepository
from app.repositories.favorite_repo import FavoriteRepository
from app.schemas.favorite_handout import FavoriteHandoutStatus
from app.services.pdf_service import PdfFileNotFoundError, PdfPathValidationError, PdfService
from app.stores.interfaces import ContentStore, PdfMappingStore

LOGGER = logging.getLogger(__name__)

HANDOUT_TITLE = "收藏讲义"
HANDOUT_NO_FAVORITES_CODE = 4091
HANDOUT_SOURCE_PDF_MISSING_CODE = 4092
HANDOUT_NOT_FOUND_CODE = 4041
HANDOUT_MERGE_FAILED_CODE = 5004
HANDOUT_EXPIRED_CODE = 4101
HANDOUT_FILE_MISSING_CODE = 5005
HANDOUT_FONT_UNAVAILABLE_CODE = 5201
HANDOUT_TOC_GENERATION_FAILED_CODE = 5202
HANDOUT_PAGE_NUMBERING_FAILED_CODE = 5203
HANDOUT_OUTPUT_INVALID_CODE = 5204

HANDOUT_NOT_FOUND_ERROR = "HANDOUT_NOT_FOUND"
HANDOUT_EXPIRED_ERROR = "HANDOUT_EXPIRED"
HANDOUT_FILE_MISSING_ERROR = "HANDOUT_FILE_MISSING"
HANDOUT_NO_FAVORITES_ERROR = "NO_FAVORITES"
HANDOUT_SOURCE_PDF_MISSING_ERROR = "HANDOUT_SOURCE_PDF_MISSING"
HANDOUT_MERGE_FAILED_ERROR = "HANDOUT_MERGE_FAILED"
HANDOUT_FONT_UNAVAILABLE_ERROR = "HANDOUT_FONT_UNAVAILABLE"
HANDOUT_TOC_GENERATION_FAILED_ERROR = "HANDOUT_TOC_GENERATION_FAILED"
HANDOUT_PAGE_NUMBERING_FAILED_ERROR = "HANDOUT_PAGE_NUMBERING_FAILED"
HANDOUT_OUTPUT_INVALID_ERROR = "HANDOUT_OUTPUT_INVALID"

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
A4_WIDTH_PT = 595.2755905511812
A4_HEIGHT_PT = 841.8897637795277
TOC_RENDER_DPI = 180
FOOTER_RENDER_DPI = 180

TOC_MARGIN_LEFT_MM = 16.0
TOC_MARGIN_RIGHT_MM = 16.0
TOC_MARGIN_TOP_MM = 14.0
TOC_MARGIN_BOTTOM_MM = 14.0
TOC_LINE_HEIGHT_MM = 6.0
TOC_ENTRY_GAP_MM = 1.2
TOC_TITLE_FONT_SIZE_PT = 22
TOC_META_FONT_SIZE_PT = 11
TOC_SECTION_FONT_SIZE_PT = 15
TOC_ENTRY_FONT_SIZE_PT = 11
TOC_PAGE_HINT_FONT_SIZE_PT = 11
TOC_QRCODE_CAPTION_FONT_SIZE_PT = 9
TOC_QRCODE_CAPTION_TEXT = "扫码进入小程序继续学习"
TOC_QRCODE_ENTRY_GAP_MM = 3.0
A4_CONTENT_MARGIN_MM = 8.0

COMMON_CJK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
)


@dataclass(frozen=True)
class FavoriteHandoutPdfFile:
    absolute_path: Path
    filename: str


@dataclass(frozen=True)
class SourcePdfEntry:
    order: int
    conclusion_id: str
    title: str
    source_pdf_path: Path
    source_page_count: int


@dataclass(frozen=True)
class TocEntry:
    order: int
    title: str
    start_page: int


@dataclass(frozen=True)
class TocBuildResult:
    toc_pdf_path: Path
    toc_page_count: int
    toc_entries: list[TocEntry]
    total_pages: int


def _mask_user_id(user_id: str) -> str:
    return mask_sensitive(user_id, left=2, right=2)


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolve_timezone() -> timezone | ZoneInfo:
    timezone_name = settings.HANDOUT_TIMEZONE.strip()
    if not timezone_name:
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name in {"Asia/Shanghai", "Asia/Chongqing", "Asia/Harbin"}:
            return timezone(timedelta(hours=8))
        LOGGER.warning(
            "favorite handout timezone invalid | request_id=%s timezone=%s fallback=UTC",
            get_request_id(),
            timezone_name,
        )
        return timezone.utc


def _as_display_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(_resolve_timezone())


def _display_date_text(value: datetime) -> str:
    display = _as_display_datetime(value) or value
    return display.strftime("%Y年%m月%d日")


def _build_public_filename(created_at: datetime, item_count: int) -> str:
    display_date = _as_display_datetime(created_at)
    date_part = display_date.strftime("%Y%m%d") if display_date else _now_utc_naive().strftime("%Y%m%d")
    return f"{HANDOUT_TITLE}_{date_part}_{item_count}条.pdf"


def _safe_expire_days() -> int:
    return settings.HANDOUT_EXPIRE_DAYS if settings.HANDOUT_EXPIRE_DAYS > 0 else 7


def _mm_to_pt(mm_value: float) -> float:
    return mm_value * PT_PER_INCH / MM_PER_INCH


def _pt_to_px(pt_value: float, dpi: int) -> int:
    px = int(round(pt_value * dpi / PT_PER_INCH))
    return px if px > 0 else 1


def _pt_value(value: Decimal | float | int) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


class FavoriteHandoutService:
    @staticmethod
    def create_from_current_user_favorites(
        *,
        db: Session,
        user_id: str,
        content_store: ContentStore,
        pdf_mapping_store: PdfMappingStore,
    ) -> dict:
        started_at = time.perf_counter()
        LOGGER.info(
            "favorite handout create start | request_id=%s user_id=%s",
            get_request_id(),
            _mask_user_id(user_id),
        )

        snapshot_conclusion_ids = FavoriteRepository.list_ids_in_default_order(db, user_id)
        if not snapshot_conclusion_ids:
            raise BizException(
                code=HANDOUT_NO_FAVORITES_CODE,
                message="当前没有可生成讲义的收藏内容",
                status_code=409,
                extra={"error_code": HANDOUT_NO_FAVORITES_ERROR},
            )

        source_entries = FavoriteHandoutService._build_source_pdf_entries(
            snapshot_conclusion_ids=snapshot_conclusion_ids,
            content_store=content_store,
            pdf_mapping_store=pdf_mapping_store,
        )
        source_total_pages = sum(entry.source_page_count for entry in source_entries)
        item_count = len(source_entries)

        handout_id = FavoriteHandoutService._generate_handout_id()
        created_at = _now_utc_naive()
        expires_at = created_at + timedelta(days=_safe_expire_days())
        filename = _build_public_filename(created_at=created_at, item_count=item_count)
        stored_filename = FavoriteHandoutService._build_stored_filename(handout_id=handout_id)
        output_dir = FavoriteHandoutService._ensure_output_dir()
        output_path = output_dir / stored_filename
        temp_dir = output_dir / f".tmp_{handout_id}_{secrets.token_hex(5)}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            toc_result = FavoriteHandoutService._build_final_toc_pdf_until_stable(
                source_entries=source_entries,
                created_at=created_at,
                temp_dir=temp_dir,
            )

            merged_without_footer = temp_dir / "merged_without_footer.pdf"
            FavoriteHandoutService._merge_toc_and_source_pdfs(
                toc_pdf_path=toc_result.toc_pdf_path,
                source_entries=source_entries,
                merged_output_path=merged_without_footer,
            )

            final_tmp_output = temp_dir / "final_handout.tmp.pdf"
            footer_applied = False
            if settings.HANDOUT_FOOTER_ENABLED:
                if FavoriteHandoutService._has_footer_collision_risk(source_entries):
                    LOGGER.warning(
                        (
                            "favorite handout footer skipped due collision risk | request_id=%s "
                            "user_id=%s handout_id=%s"
                        ),
                        get_request_id(),
                        _mask_user_id(user_id),
                        handout_id,
                    )
                    FavoriteHandoutService._copy_file(merged_without_footer, final_tmp_output)
                else:
                    FavoriteHandoutService._apply_unified_page_numbers(
                        input_pdf_path=merged_without_footer,
                        final_output_path=final_tmp_output,
                        temp_dir=temp_dir,
                    )
                    footer_applied = True
            else:
                FavoriteHandoutService._copy_file(merged_without_footer, final_tmp_output)

            expected_total_pages = toc_result.toc_page_count + source_total_pages
            validated_page_count = FavoriteHandoutService._validate_output_pdf(
                output_pdf_path=final_tmp_output,
                expected_total_pages=expected_total_pages,
            )
            file_size = final_tmp_output.stat().st_size if final_tmp_output.exists() else 0
            FavoriteHandoutService._replace_file_atomically(
                temp_path=final_tmp_output,
                final_path=output_path,
            )

            record = FavoriteHandoutRepository.create(
                db=db,
                handout_id=handout_id,
                user_id=user_id,
                title=HANDOUT_TITLE,
                status=FavoriteHandoutStatus.ready.value,
                item_count=item_count,
                filename=filename,
                stored_filename=stored_filename,
                snapshot_conclusion_ids_json=json.dumps(
                    snapshot_conclusion_ids,
                    ensure_ascii=False,
                ),
                created_at=created_at,
                expires_at=expires_at,
            )
        except BizException:
            raise
        except Exception:
            LOGGER.exception(
                "favorite handout pipeline failed | request_id=%s user_id=%s handout_id=%s",
                get_request_id(),
                _mask_user_id(user_id),
                handout_id,
            )
            raise BizException(
                code=HANDOUT_MERGE_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_MERGE_FAILED_ERROR},
            )
        finally:
            FavoriteHandoutService._cleanup_temp_files(temp_dir)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        LOGGER.info(
            (
                "favorite handout create success | request_id=%s user_id=%s handout_id=%s "
                "item_count=%s source_pages=%s total_pages=%s footer_applied=%s output_bytes=%s elapsed_ms=%s"
            ),
            get_request_id(),
            _mask_user_id(user_id),
            handout_id,
            item_count,
            source_total_pages,
            validated_page_count,
            str(footer_applied).lower(),
            file_size,
            elapsed_ms,
        )
        return FavoriteHandoutService._to_response_payload(record)

    @staticmethod
    def get_handout(
        *,
        db: Session,
        user_id: str,
        handout_id: str,
    ) -> dict:
        record = FavoriteHandoutRepository.get_by_handout_id_and_user_id(
            db=db,
            handout_id=handout_id,
            user_id=user_id,
        )
        if record is None:
            raise BizException(
                code=HANDOUT_NOT_FOUND_CODE,
                message="收藏讲义不存在",
                status_code=404,
                extra={"error_code": HANDOUT_NOT_FOUND_ERROR},
            )
        return FavoriteHandoutService._to_response_payload(record)

    @staticmethod
    def get_handout_pdf(
        *,
        db: Session,
        user_id: str,
        handout_id: str,
    ) -> FavoriteHandoutPdfFile:
        record = FavoriteHandoutRepository.get_by_handout_id_and_user_id(
            db=db,
            handout_id=handout_id,
            user_id=user_id,
        )
        if record is None:
            raise BizException(
                code=HANDOUT_NOT_FOUND_CODE,
                message="收藏讲义不存在",
                status_code=404,
                extra={"error_code": HANDOUT_NOT_FOUND_ERROR},
            )

        if FavoriteHandoutService._is_expired(record):
            raise BizException(
                code=HANDOUT_EXPIRED_CODE,
                message="收藏讲义已过期，请重新生成",
                status_code=410,
                extra={"error_code": HANDOUT_EXPIRED_ERROR},
            )

        if not record.stored_filename:
            raise BizException(
                code=HANDOUT_FILE_MISSING_CODE,
                message="讲义文件不可用，请重新生成",
                status_code=500,
                extra={"error_code": HANDOUT_FILE_MISSING_ERROR},
            )

        try:
            pdf_file = PdfService.resolve_pdf_file(
                file_path=record.stored_filename,
                raw_root_dir=settings.HANDOUT_OUTPUT_DIR,
            )
        except (PdfPathValidationError, PdfFileNotFoundError):
            raise BizException(
                code=HANDOUT_FILE_MISSING_CODE,
                message="讲义文件不可用，请重新生成",
                status_code=500,
                extra={"error_code": HANDOUT_FILE_MISSING_ERROR},
            )

        return FavoriteHandoutPdfFile(
            absolute_path=pdf_file.absolute_path,
            filename=record.filename
            or _build_public_filename(created_at=record.created_at, item_count=record.item_count),
        )

    @staticmethod
    def _build_source_pdf_entries(
        *,
        snapshot_conclusion_ids: list[str],
        content_store: ContentStore,
        pdf_mapping_store: PdfMappingStore,
    ) -> list[SourcePdfEntry]:
        missing_items: list[dict[str, str]] = []
        entries: list[SourcePdfEntry] = []

        for index, conclusion_id in enumerate(snapshot_conclusion_ids, start=1):
            title = FavoriteHandoutService._resolve_conclusion_title(
                content_store=content_store,
                conclusion_id=conclusion_id,
            )
            try:
                pdf_file = PdfService.resolve_conclusion_pdf_file(
                    conclusion_id=conclusion_id,
                    pdf_mapping_store=pdf_mapping_store,
                    raw_root_dir=settings.PDF_ROOT_DIR,
                )
            except (PdfPathValidationError, PdfFileNotFoundError):
                pdf_file = None

            if not pdf_file:
                missing_items.append(
                    {
                        "conclusion_id": conclusion_id,
                        "title": title,
                    }
                )
                continue

            page_count = FavoriteHandoutService._read_source_pdf_page_count(
                source_pdf_path=pdf_file.absolute_path
            )
            if page_count <= 0:
                missing_items.append(
                    {
                        "conclusion_id": conclusion_id,
                        "title": title,
                    }
                )
                continue

            entries.append(
                SourcePdfEntry(
                    order=index,
                    conclusion_id=conclusion_id,
                    title=title,
                    source_pdf_path=pdf_file.absolute_path,
                    source_page_count=page_count,
                )
            )

        if missing_items:
            LOGGER.warning(
                "favorite handout source missing | request_id=%s missing_count=%s missing_ids=%s",
                get_request_id(),
                len(missing_items),
                [item["conclusion_id"] for item in missing_items],
            )
            raise BizException(
                code=HANDOUT_SOURCE_PDF_MISSING_CODE,
                message="部分收藏内容暂无可用 PDF，暂时无法生成讲义",
                status_code=409,
                extra={
                    "error_code": HANDOUT_SOURCE_PDF_MISSING_ERROR,
                    "missing_items": missing_items,
                },
            )

        return entries

    @staticmethod
    def _read_source_pdf_page_count(*, source_pdf_path: Path) -> int:
        from pikepdf import Pdf

        try:
            with Pdf.open(str(source_pdf_path)) as source_pdf:
                return len(source_pdf.pages)
        except Exception:
            LOGGER.warning(
                "favorite handout page count read failed | request_id=%s file=%s",
                get_request_id(),
                source_pdf_path.name,
            )
            return 0

    @staticmethod
    def _calculate_toc_entries_with_start_pages(
        source_entries: list[SourcePdfEntry],
        toc_page_count: int,
    ) -> list[TocEntry]:
        current_page = toc_page_count + 1
        result: list[TocEntry] = []
        for entry in source_entries:
            result.append(
                TocEntry(
                    order=entry.order,
                    title=entry.title,
                    start_page=current_page,
                )
            )
            current_page += entry.source_page_count
        return result

    @staticmethod
    def _build_final_toc_pdf_until_stable(
        *,
        source_entries: list[SourcePdfEntry],
        created_at: datetime,
        temp_dir: Path,
    ) -> TocBuildResult:
        source_total_pages = sum(entry.source_page_count for entry in source_entries)
        max_iterations = (
            settings.HANDOUT_TOC_MAX_ITERATIONS
            if settings.HANDOUT_TOC_MAX_ITERATIONS > 0
            else 3
        )

        guess_toc_pages = 1
        last_page_count = 0
        last_entries: list[TocEntry] = []
        last_pdf_path: Path | None = None

        for index in range(1, max_iterations + 1):
            toc_entries = FavoriteHandoutService._calculate_toc_entries_with_start_pages(
                source_entries=source_entries,
                toc_page_count=guess_toc_pages,
            )
            total_pages = source_total_pages + guess_toc_pages
            toc_path = temp_dir / f"toc_iter_{index}.pdf"
            actual_toc_pages = FavoriteHandoutService._render_toc_pdf(
                entries_with_pages=toc_entries,
                item_count=len(source_entries),
                total_pages=total_pages,
                created_at=created_at,
                output_path=toc_path,
            )
            last_page_count = actual_toc_pages
            last_entries = toc_entries
            last_pdf_path = toc_path
            if actual_toc_pages == guess_toc_pages:
                final_toc_path = temp_dir / "toc_final.pdf"
                FavoriteHandoutService._copy_file(toc_path, final_toc_path)
                return TocBuildResult(
                    toc_pdf_path=final_toc_path,
                    toc_page_count=actual_toc_pages,
                    toc_entries=toc_entries,
                    total_pages=source_total_pages + actual_toc_pages,
                )
            guess_toc_pages = actual_toc_pages

        LOGGER.error(
            (
                "favorite handout toc stabilize failed | request_id=%s last_toc_pages=%s "
                "max_iterations=%s"
            ),
            get_request_id(),
            last_page_count,
            max_iterations,
        )
        raise BizException(
            code=HANDOUT_TOC_GENERATION_FAILED_CODE,
            message="收藏讲义生成失败，请稍后重试",
            status_code=500,
            extra={"error_code": HANDOUT_TOC_GENERATION_FAILED_ERROR},
        )

    @staticmethod
    def _render_toc_pdf(
        *,
        entries_with_pages: list[TocEntry],
        item_count: int,
        total_pages: int,
        created_at: datetime,
        output_path: Path,
    ) -> int:
        try:
            from PIL import Image, ImageDraw
        except Exception:
            LOGGER.exception("favorite handout toc generator unavailable | request_id=%s", get_request_id())
            raise BizException(
                code=HANDOUT_TOC_GENERATION_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_TOC_GENERATION_FAILED_ERROR},
            )

        font_path = FavoriteHandoutService._ensure_cjk_font_path()

        def _font(size_pt: int):
            return FavoriteHandoutService._load_cjk_font(font_path=font_path, size_pt=size_pt)

        width_px = _pt_to_px(A4_WIDTH_PT, TOC_RENDER_DPI)
        height_px = _pt_to_px(A4_HEIGHT_PT, TOC_RENDER_DPI)
        left_px = _pt_to_px(_mm_to_pt(TOC_MARGIN_LEFT_MM), TOC_RENDER_DPI)
        right_px = width_px - _pt_to_px(_mm_to_pt(TOC_MARGIN_RIGHT_MM), TOC_RENDER_DPI)
        top_px = _pt_to_px(_mm_to_pt(TOC_MARGIN_TOP_MM), TOC_RENDER_DPI)
        bottom_px = height_px - _pt_to_px(_mm_to_pt(TOC_MARGIN_BOTTOM_MM), TOC_RENDER_DPI)
        line_height_px = _pt_to_px(_mm_to_pt(TOC_LINE_HEIGHT_MM), TOC_RENDER_DPI)
        entry_gap_px = _pt_to_px(_mm_to_pt(TOC_ENTRY_GAP_MM), TOC_RENDER_DPI)

        title_font = _font(TOC_TITLE_FONT_SIZE_PT)
        meta_font = _font(TOC_META_FONT_SIZE_PT)
        section_font = _font(TOC_SECTION_FONT_SIZE_PT)
        entry_font = _font(TOC_ENTRY_FONT_SIZE_PT)
        hint_font = _font(TOC_PAGE_HINT_FONT_SIZE_PT)
        qrcode_caption_font = _font(TOC_QRCODE_CAPTION_FONT_SIZE_PT)

        page_images: list[Any] = []

        def _new_page() -> tuple[Any, Any, int]:
            image = Image.new("RGB", (width_px, height_px), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            page_images.append(image)
            return image, draw, len(page_images) - 1

        def _text_width(draw: Any, text: str, font: Any) -> int:
            bbox = draw.textbbox((0, 0), text, font=font)
            return int(bbox[2] - bbox[0])

        def _text_height(draw: Any, text: str, font: Any) -> int:
            bbox = draw.textbbox((0, 0), text, font=font)
            return int(bbox[3] - bbox[1])

        def _wrap_text(draw: Any, text: str, max_width: int, font: Any) -> list[str]:
            if not text:
                return [""]
            lines: list[str] = []
            current = ""
            for char in text:
                candidate = current + char
                if _text_width(draw, candidate, font) <= max_width:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                    current = char
                else:
                    lines.append(char)
                    current = ""
            if current:
                lines.append(current)
            return lines or [""]

        qrcode_image: Any | None = None
        qrcode_size_px = 0
        qrcode_bottom_px = 0
        qrcode_caption_height_px = 0
        qrcode_entry_gap_px = _pt_to_px(_mm_to_pt(TOC_QRCODE_ENTRY_GAP_MM), TOC_RENDER_DPI)

        qrcode_path = FavoriteHandoutService._resolve_miniapp_qrcode_path()
        if qrcode_path is not None:
            try:
                qrcode_image = Image.open(str(qrcode_path)).convert("RGBA")
                qrcode_size_mm = (
                    settings.HANDOUT_MINIAPP_QRCODE_SIZE_MM
                    if settings.HANDOUT_MINIAPP_QRCODE_SIZE_MM > 0
                    else 20
                )
                qrcode_bottom_mm = (
                    settings.HANDOUT_MINIAPP_QRCODE_BOTTOM_MM
                    if settings.HANDOUT_MINIAPP_QRCODE_BOTTOM_MM >= 0
                    else 14
                )
                qrcode_size_px = _pt_to_px(_mm_to_pt(float(qrcode_size_mm)), TOC_RENDER_DPI)
                qrcode_bottom_px = _pt_to_px(_mm_to_pt(float(qrcode_bottom_mm)), TOC_RENDER_DPI)
            except Exception:
                LOGGER.warning(
                    (
                        "favorite handout qrcode load failed, skip qrcode | request_id=%s "
                        "file=%s"
                    ),
                    get_request_id(),
                    qrcode_path.name,
                )
                qrcode_image = None

        _, draw, current_page_index = _new_page()
        if qrcode_image is not None:
            qrcode_caption_height_px = _text_height(draw, TOC_QRCODE_CAPTION_TEXT, qrcode_caption_font)

        first_page_bottom_px = bottom_px
        if qrcode_image is not None:
            reserved_top = (
                height_px
                - qrcode_bottom_px
                - qrcode_size_px
                - qrcode_caption_height_px
                - 4
            )
            first_page_bottom_px = min(first_page_bottom_px, reserved_top - qrcode_entry_gap_px)
            if first_page_bottom_px <= top_px + line_height_px * 3:
                LOGGER.warning(
                    "favorite handout qrcode skipped due layout space | request_id=%s",
                    get_request_id(),
                )
                qrcode_image = None
                first_page_bottom_px = bottom_px

        current_y = top_px
        draw.text((left_px, current_y), HANDOUT_TITLE, font=title_font, fill=(20, 20, 20))
        current_y += int(line_height_px * 1.6)
        draw.text(
            (left_px, current_y),
            f"生成时间：{_display_date_text(created_at)}",
            font=meta_font,
            fill=(50, 50, 50),
        )
        current_y += int(line_height_px * 1.1)
        draw.text(
            (left_px, current_y),
            f"包含内容：{item_count} 条结论",
            font=meta_font,
            fill=(50, 50, 50),
        )
        current_y += int(line_height_px * 1.1)
        draw.text(
            (left_px, current_y),
            f"总页数：{total_pages} 页",
            font=meta_font,
            fill=(50, 50, 50),
        )
        current_y += int(line_height_px * 1.6)
        draw.text((left_px, current_y), "目录", font=section_font, fill=(20, 20, 20))
        current_y += int(line_height_px * 1.4)

        for entry in entries_with_pages:
            seq_text = f"{entry.order:02d}"
            page_text = str(entry.start_page)
            prefix_text = f"{seq_text}  "
            prefix_width = _text_width(draw, prefix_text, entry_font)
            page_width = _text_width(draw, page_text, entry_font)
            page_x = right_px - page_width
            title_max_width = max(40, page_x - left_px - prefix_width - 24)
            title_lines = _wrap_text(draw, entry.title, title_max_width, entry_font)
            entry_height = len(title_lines) * line_height_px + entry_gap_px

            page_bottom_limit = (
                first_page_bottom_px
                if current_page_index == 0
                else bottom_px
            )

            if current_y + entry_height > page_bottom_limit:
                _, draw, current_page_index = _new_page()
                current_y = top_px
                draw.text((left_px, current_y), "目录（续）", font=hint_font, fill=(30, 30, 30))
                current_y += int(line_height_px * 1.2)

            first_line_text = prefix_text + title_lines[0]
            draw.text((left_px, current_y), first_line_text, font=entry_font, fill=(25, 25, 25))
            draw.text((page_x, current_y), page_text, font=entry_font, fill=(25, 25, 25))

            first_line_width = _text_width(draw, first_line_text, entry_font)
            dot_start_x = left_px + first_line_width + 8
            dot_end_x = page_x - 8
            if dot_end_x > dot_start_x:
                dot_width = max(1, _text_width(draw, ".", entry_font))
                dot_count = int((dot_end_x - dot_start_x) / dot_width)
                if dot_count > 0:
                    draw.text(
                        (dot_start_x, current_y),
                        "." * dot_count,
                        font=entry_font,
                        fill=(100, 100, 100),
                    )

            for extra_line in title_lines[1:]:
                current_y += line_height_px
                draw.text(
                    (left_px + prefix_width, current_y),
                    extra_line,
                    font=entry_font,
                    fill=(25, 25, 25),
                )

            current_y += line_height_px + entry_gap_px

        if qrcode_image is not None and page_images:
            qrcode_resample = (
                Image.Resampling.LANCZOS
                if hasattr(Image, "Resampling")
                else Image.LANCZOS
            )
            qrcode_resized = qrcode_image.resize(
                (qrcode_size_px, qrcode_size_px),
                qrcode_resample,
            )
            qrcode_x = right_px - qrcode_size_px
            qrcode_y = height_px - qrcode_bottom_px - qrcode_size_px
            qrcode_caption_gap_px = 4
            qrcode_caption_y = qrcode_y - qrcode_caption_height_px - qrcode_caption_gap_px

            first_page = page_images[0]
            first_page.paste(qrcode_resized, (qrcode_x, qrcode_y), qrcode_resized)
            first_draw = ImageDraw.Draw(first_page)
            caption_width = _text_width(first_draw, TOC_QRCODE_CAPTION_TEXT, qrcode_caption_font)
            caption_x = qrcode_x + int((qrcode_size_px - caption_width) / 2)
            first_draw.text(
                (caption_x, qrcode_caption_y),
                TOC_QRCODE_CAPTION_TEXT,
                font=qrcode_caption_font,
                fill=(80, 80, 80),
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not page_images:
            raise BizException(
                code=HANDOUT_TOC_GENERATION_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_TOC_GENERATION_FAILED_ERROR},
            )

        try:
            page_images[0].save(
                str(output_path),
                format="PDF",
                save_all=True,
                append_images=page_images[1:],
                resolution=TOC_RENDER_DPI,
            )
        except Exception:
            LOGGER.exception("favorite handout toc render failed | request_id=%s", get_request_id())
            raise BizException(
                code=HANDOUT_TOC_GENERATION_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_TOC_GENERATION_FAILED_ERROR},
            )

        return FavoriteHandoutService._count_pdf_pages(output_path)

    @staticmethod
    def _merge_toc_and_source_pdfs(
        *,
        toc_pdf_path: Path,
        source_entries: list[SourcePdfEntry],
        merged_output_path: Path,
    ) -> None:
        from pikepdf import Pdf

        merged = Pdf.new()
        opened: list[Any] = []
        try:
            toc_pdf = Pdf.open(str(toc_pdf_path))
            opened.append(toc_pdf)
            for toc_page in toc_pdf.pages:
                FavoriteHandoutService._append_page_to_merged_pdf(
                    merged_pdf=merged,
                    source_page=toc_page,
                )
            for entry in source_entries:
                source_pdf = Pdf.open(str(entry.source_pdf_path))
                opened.append(source_pdf)
                for source_page in source_pdf.pages:
                    FavoriteHandoutService._append_page_to_merged_pdf(
                        merged_pdf=merged,
                        source_page=source_page,
                    )
            merged.save(str(merged_output_path))
        except Exception:
            LOGGER.exception(
                "favorite handout merge toc+source failed | request_id=%s",
                get_request_id(),
            )
            raise BizException(
                code=HANDOUT_MERGE_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_MERGE_FAILED_ERROR},
            )
        finally:
            for pdf in opened:
                try:
                    pdf.close()
                except Exception:
                    pass
            try:
                merged.close()
            except Exception:
                pass

    @staticmethod
    def _append_page_to_merged_pdf(*, merged_pdf: Any, source_page: Any) -> None:
        if not settings.HANDOUT_FORCE_A4_PAGE_SIZE:
            merged_pdf.pages.append(source_page)
            return

        from pikepdf import Rectangle

        target_page = merged_pdf.add_blank_page(page_size=(A4_WIDTH_PT, A4_HEIGHT_PT))
        margin_pt = _mm_to_pt(A4_CONTENT_MARGIN_MM)
        target_rect = Rectangle(
            margin_pt,
            margin_pt,
            A4_WIDTH_PT - margin_pt,
            A4_HEIGHT_PT - margin_pt,
        )
        target_page.add_overlay(source_page, target_rect, shrink=True, expand=False)

    @staticmethod
    def _render_page_number_overlay(
        *,
        page_width_pt: float,
        page_height_pt: float,
        page_number: int,
        total_pages: int,
        overlay_path: Path,
    ) -> None:
        try:
            from PIL import Image, ImageDraw
        except Exception:
            LOGGER.exception("favorite handout footer renderer unavailable | request_id=%s", get_request_id())
            raise BizException(
                code=HANDOUT_PAGE_NUMBERING_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_PAGE_NUMBERING_FAILED_ERROR},
            )

        font_path = FavoriteHandoutService._ensure_cjk_font_path()
        font_size = settings.HANDOUT_FOOTER_FONT_SIZE if settings.HANDOUT_FOOTER_FONT_SIZE > 0 else 9
        footer_font = FavoriteHandoutService._load_cjk_font(
            font_path=font_path,
            size_pt=font_size,
        )
        width_px = _pt_to_px(page_width_pt, FOOTER_RENDER_DPI)
        height_px = _pt_to_px(page_height_pt, FOOTER_RENDER_DPI)
        image = Image.new("RGBA", (width_px, height_px), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        text = f"{HANDOUT_TITLE} · 第 {page_number} / {total_pages} 页"
        bbox = draw.textbbox((0, 0), text, font=footer_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = int((width_px - text_width) / 2)
        footer_y_mm = settings.HANDOUT_FOOTER_Y_MM if settings.HANDOUT_FOOTER_Y_MM >= 0 else 8
        footer_y_pt = _mm_to_pt(float(footer_y_mm))
        text_y = int(height_px - _pt_to_px(footer_y_pt, FOOTER_RENDER_DPI) - text_height)
        text_y = max(0, text_y)
        draw.text(
            (text_x, text_y),
            text,
            font=footer_font,
            fill=(80, 80, 80, 185),
        )
        image.save(str(overlay_path), format="PDF", resolution=FOOTER_RENDER_DPI)

    @staticmethod
    def _apply_unified_page_numbers(
        *,
        input_pdf_path: Path,
        final_output_path: Path,
        temp_dir: Path,
    ) -> None:
        from pikepdf import Pdf

        try:
            with Pdf.open(str(input_pdf_path)) as input_pdf:
                total_pages = len(input_pdf.pages)
                for index, page in enumerate(input_pdf.pages, start=1):
                    page_width = _pt_value(page.MediaBox[2]) - _pt_value(page.MediaBox[0])
                    page_height = _pt_value(page.MediaBox[3]) - _pt_value(page.MediaBox[1])
                    overlay_path = temp_dir / f"footer_overlay_{index}.pdf"
                    FavoriteHandoutService._render_page_number_overlay(
                        page_width_pt=page_width,
                        page_height_pt=page_height,
                        page_number=index,
                        total_pages=total_pages,
                        overlay_path=overlay_path,
                    )
                    with Pdf.open(str(overlay_path)) as overlay_pdf:
                        overlay_page = overlay_pdf.pages[0]
                        page.add_overlay(overlay_page)
                input_pdf.save(str(final_output_path))
        except BizException:
            raise
        except Exception:
            LOGGER.exception("favorite handout footer apply failed | request_id=%s", get_request_id())
            raise BizException(
                code=HANDOUT_PAGE_NUMBERING_FAILED_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_PAGE_NUMBERING_FAILED_ERROR},
            )

    @staticmethod
    def _validate_output_pdf(*, output_pdf_path: Path, expected_total_pages: int) -> int:
        if not output_pdf_path.exists():
            raise BizException(
                code=HANDOUT_OUTPUT_INVALID_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_OUTPUT_INVALID_ERROR},
            )
        if output_pdf_path.stat().st_size <= 0:
            raise BizException(
                code=HANDOUT_OUTPUT_INVALID_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_OUTPUT_INVALID_ERROR},
            )
        page_count = FavoriteHandoutService._count_pdf_pages(output_pdf_path)
        if page_count != expected_total_pages:
            LOGGER.error(
                (
                    "favorite handout page count mismatch | request_id=%s expected=%s actual=%s"
                ),
                get_request_id(),
                expected_total_pages,
                page_count,
            )
            raise BizException(
                code=HANDOUT_OUTPUT_INVALID_CODE,
                message="收藏讲义生成失败，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_OUTPUT_INVALID_ERROR},
            )
        return page_count

    @staticmethod
    def _count_pdf_pages(pdf_path: Path) -> int:
        from pikepdf import Pdf

        with Pdf.open(str(pdf_path)) as pdf:
            return len(pdf.pages)

    @staticmethod
    def _resolve_conclusion_title(content_store: ContentStore, conclusion_id: str) -> str:
        summary = content_store.get_summary(conclusion_id)
        if not summary:
            return conclusion_id
        raw_title = str(summary.get("title") or "").strip()
        title = FavoriteHandoutService._normalize_display_title(raw_title)
        if not title:
            return conclusion_id
        if title.count("?") >= max(2, len(title) // 2):
            return conclusion_id
        return title

    @staticmethod
    def _normalize_display_title(value: str) -> str:
        text = value.strip()
        if not text:
            return ""

        # Attempt to repair common mojibake patterns from legacy encoding mismatches.
        for src_encoding in ("latin-1", "cp1252", "gbk"):
            try:
                candidate = text.encode(src_encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            candidate = candidate.strip()
            if not candidate:
                continue
            if candidate != text and FavoriteHandoutService._contains_cjk(candidate):
                return candidate

        return text

    @staticmethod
    def _contains_cjk(value: str) -> bool:
        for ch in value:
            code = ord(ch)
            if (
                0x4E00 <= code <= 0x9FFF
                or 0x3400 <= code <= 0x4DBF
                or 0x20000 <= code <= 0x2A6DF
                or 0x2A700 <= code <= 0x2B73F
                or 0x2B740 <= code <= 0x2B81F
                or 0x2B820 <= code <= 0x2CEAF
                or 0xF900 <= code <= 0xFAFF
            ):
                return True
        return False

    @staticmethod
    def _generate_handout_id() -> str:
        return f"fh_{secrets.token_hex(12)}"

    @staticmethod
    def _build_stored_filename(*, handout_id: str) -> str:
        return f"{handout_id}_{secrets.token_hex(6)}.pdf"

    @staticmethod
    def _ensure_output_dir() -> Path:
        output_dir = PdfService.resolve_pdf_root(settings.HANDOUT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def _resolve_font_path(raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        project_root = Path(__file__).resolve().parents[2]
        return (project_root / path).resolve()

    @staticmethod
    def _resolve_miniapp_qrcode_path() -> Path | None:
        if not settings.HANDOUT_MINIAPP_QRCODE_ENABLED:
            return None

        configured = settings.HANDOUT_MINIAPP_QRCODE_PATH.strip()
        if not configured:
            return None

        resolved = FavoriteHandoutService._resolve_font_path(configured)
        if resolved.is_file():
            return resolved

        LOGGER.warning(
            "favorite handout miniapp qrcode missing, skip qrcode | request_id=%s file=%s",
            get_request_id(),
            configured,
        )
        return None

    @staticmethod
    def _ensure_cjk_font_path() -> Path:
        configured = settings.HANDOUT_CJK_FONT_PATH.strip()
        if configured:
            resolved = FavoriteHandoutService._resolve_font_path(configured)
            if resolved.is_file():
                return resolved
            LOGGER.error(
                "favorite handout font configured but missing | request_id=%s font=%s",
                get_request_id(),
                configured,
            )
            raise BizException(
                code=HANDOUT_FONT_UNAVAILABLE_CODE,
                message="讲义生成服务暂不可用，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_FONT_UNAVAILABLE_ERROR},
            )

        for candidate in COMMON_CJK_FONT_CANDIDATES:
            resolved = FavoriteHandoutService._resolve_font_path(candidate)
            if resolved.is_file():
                return resolved

        LOGGER.error(
            "favorite handout font unavailable | request_id=%s candidates=%s",
            get_request_id(),
            len(COMMON_CJK_FONT_CANDIDATES),
        )
        raise BizException(
            code=HANDOUT_FONT_UNAVAILABLE_CODE,
            message="讲义生成服务暂不可用，请稍后重试",
            status_code=500,
            extra={"error_code": HANDOUT_FONT_UNAVAILABLE_ERROR},
        )

    @staticmethod
    def _load_cjk_font(*, font_path: Path, size_pt: int):
        try:
            from PIL import ImageFont
        except Exception:
            raise BizException(
                code=HANDOUT_FONT_UNAVAILABLE_CODE,
                message="讲义生成服务暂不可用，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_FONT_UNAVAILABLE_ERROR},
            )

        try:
            return ImageFont.truetype(str(font_path), size=size_pt)
        except Exception:
            LOGGER.exception(
                "favorite handout font load failed | request_id=%s font=%s",
                get_request_id(),
                font_path.name,
            )
            raise BizException(
                code=HANDOUT_FONT_UNAVAILABLE_CODE,
                message="讲义生成服务暂不可用，请稍后重试",
                status_code=500,
                extra={"error_code": HANDOUT_FONT_UNAVAILABLE_ERROR},
            )

    @staticmethod
    def _copy_file(src_path: Path, dst_path: Path) -> None:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(src_path.read_bytes())

    @staticmethod
    def _replace_file_atomically(*, temp_path: Path, final_path: Path) -> None:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_path.replace(final_path)
            return
        except PermissionError:
            FavoriteHandoutService._copy_file(temp_path, final_path)

    @staticmethod
    def _cleanup_temp_files(temp_dir: Path) -> None:
        if not temp_dir.exists():
            return
        for _ in range(3):
            try:
                shutil.rmtree(temp_dir)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                time.sleep(0.05)
            except OSError:
                time.sleep(0.05)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _to_response_payload(record: FavoriteHandout) -> dict:
        if FavoriteHandoutService._is_expired(record):
            status = FavoriteHandoutStatus.expired.value
        else:
            status = record.status

        error_payload = None
        if record.failure_code or record.failure_message:
            error_payload = {
                "code": record.failure_code or "",
                "message": record.failure_message or "",
            }

        return {
            "handout_id": record.handout_id,
            "title": record.title,
            "status": status,
            "item_count": record.item_count,
            "filename": record.filename,
            "pdf_url": f"/api/v1/favorites/handouts/{record.handout_id}/pdf",
            "created_at": _as_display_datetime(record.created_at),
            "expires_at": _as_display_datetime(record.expires_at),
            "error": error_payload,
        }

    @staticmethod
    def _is_expired(record: FavoriteHandout) -> bool:
        if record.expires_at is None:
            return False
        return record.expires_at <= _now_utc_naive()

    @staticmethod
    def _has_footer_collision_risk(source_entries: list[SourcePdfEntry]) -> bool:
        """Probe a few source pages and avoid footer overlay when obvious bottom text exists."""
        from pikepdf import Pdf, parse_content_stream

        footer_y_mm = settings.HANDOUT_FOOTER_Y_MM if settings.HANDOUT_FOOTER_Y_MM >= 0 else 8
        footer_y_pt = _mm_to_pt(float(footer_y_mm))
        threshold_pt = footer_y_pt + _mm_to_pt(4.0)

        for entry in source_entries[:3]:
            try:
                with Pdf.open(str(entry.source_pdf_path)) as source_pdf:
                    if not source_pdf.pages:
                        continue
                    first_page = source_pdf.pages[0]
                    cursor_y: float | None = None
                    current_font_size = 0.0
                    for instruction in parse_content_stream(first_page):
                        operator = str(instruction.operator)
                        operands = instruction.operands
                        if operator == "Tf" and len(operands) >= 2:
                            try:
                                current_font_size = float(operands[1])
                            except Exception:
                                current_font_size = 0.0
                            continue
                        if operator == "Tm" and len(operands) == 6:
                            try:
                                cursor_y = float(operands[5])
                            except Exception:
                                cursor_y = None
                            continue
                        if operator in {"Td", "TD"} and len(operands) == 2:
                            try:
                                delta = float(operands[1])
                                cursor_y = (cursor_y or 0.0) + delta
                            except Exception:
                                pass
                            continue
                        if operator in {"Tj", "TJ", "'", '"'}:
                            if cursor_y is not None and cursor_y <= threshold_pt and current_font_size >= 6:
                                return True
            except Exception:
                # Parsing failure should not block the generation pipeline.
                LOGGER.debug(
                    "favorite handout footer risk scan skipped page | request_id=%s file=%s",
                    get_request_id(),
                    entry.source_pdf_path.name,
                )
                continue
        return False
