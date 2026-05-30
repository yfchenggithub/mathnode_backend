from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
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

HANDOUT_NOT_FOUND_ERROR = "HANDOUT_NOT_FOUND"
HANDOUT_EXPIRED_ERROR = "HANDOUT_EXPIRED"
HANDOUT_FILE_MISSING_ERROR = "HANDOUT_FILE_MISSING"
HANDOUT_NO_FAVORITES_ERROR = "NO_FAVORITES"
HANDOUT_SOURCE_PDF_MISSING_ERROR = "HANDOUT_SOURCE_PDF_MISSING"
HANDOUT_MERGE_FAILED_ERROR = "HANDOUT_MERGE_FAILED"


def _mask_user_id(user_id: str) -> str:
    return mask_sensitive(user_id, left=2, right=2)


def _resolve_timezone():
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


def _build_public_filename(created_at: datetime) -> str:
    display_date = _as_display_datetime(created_at)
    date_part = display_date.strftime("%Y%m%d") if display_date else datetime.utcnow().strftime("%Y%m%d")
    return f"{HANDOUT_TITLE}_{date_part}.pdf"


def _safe_expire_days() -> int:
    return settings.HANDOUT_EXPIRE_DAYS if settings.HANDOUT_EXPIRE_DAYS > 0 else 7


@dataclass(frozen=True)
class FavoriteHandoutPdfFile:
    absolute_path: Path
    filename: str


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

        missing_items: list[dict[str, str]] = []
        source_pdf_paths: list[Path] = []

        for conclusion_id in snapshot_conclusion_ids:
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

            source_pdf_paths.append(pdf_file.absolute_path)

        if missing_items:
            LOGGER.warning(
                "favorite handout source missing | request_id=%s user_id=%s missing_count=%s missing_ids=%s",
                get_request_id(),
                _mask_user_id(user_id),
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

        handout_id = FavoriteHandoutService._generate_handout_id()
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=_safe_expire_days())
        filename = _build_public_filename(created_at)
        stored_filename = FavoriteHandoutService._build_stored_filename(handout_id=handout_id)
        output_dir = FavoriteHandoutService._ensure_output_dir()
        output_path = output_dir / stored_filename

        try:
            file_size = FavoriteHandoutService._merge_pdf_files(
                source_pdf_paths=source_pdf_paths,
                output_path=output_path,
            )
        except Exception:
            LOGGER.exception(
                "favorite handout merge failed | request_id=%s user_id=%s handout_id=%s",
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

        record = FavoriteHandoutRepository.create(
            db=db,
            handout_id=handout_id,
            user_id=user_id,
            title=HANDOUT_TITLE,
            status=FavoriteHandoutStatus.ready.value,
            item_count=len(snapshot_conclusion_ids),
            filename=filename,
            stored_filename=stored_filename,
            snapshot_conclusion_ids_json=json.dumps(
                snapshot_conclusion_ids,
                ensure_ascii=False,
            ),
            created_at=created_at,
            expires_at=expires_at,
        )

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        LOGGER.info(
            (
                "favorite handout create success | request_id=%s user_id=%s handout_id=%s "
                "item_count=%s output_bytes=%s elapsed_ms=%s"
            ),
            get_request_id(),
            _mask_user_id(user_id),
            handout_id,
            len(snapshot_conclusion_ids),
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
            filename=record.filename or _build_public_filename(record.created_at),
        )

    @staticmethod
    def _resolve_conclusion_title(content_store: ContentStore, conclusion_id: str) -> str:
        summary = content_store.get_summary(conclusion_id)
        if not summary:
            return conclusion_id
        title = str(summary.get("title") or "").strip()
        return title or conclusion_id

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
    def _merge_pdf_files(
        *,
        source_pdf_paths: list[Path],
        output_path: Path,
    ) -> int:
        temp_path = output_path.parent / f".{output_path.name}.{secrets.token_hex(4)}.tmp"
        from pikepdf import Pdf

        merged_pdf = Pdf.new()
        source_pdfs = []
        try:
            for source_path in source_pdf_paths:
                source_pdf = Pdf.open(str(source_path))
                source_pdfs.append(source_pdf)
                merged_pdf.pages.extend(source_pdf.pages)

            output_buffer = BytesIO()
            merged_pdf.save(output_buffer)
            payload = output_buffer.getvalue()
            temp_path.write_bytes(payload)

            for source_pdf in source_pdfs:
                source_pdf.close()
            source_pdfs.clear()
            merged_pdf.close()

            if not temp_path.exists():
                raise RuntimeError("temporary handout pdf missing after merge")
            if temp_path.stat().st_size <= 0:
                raise RuntimeError("temporary handout pdf is empty")

            try:
                temp_path.replace(output_path)
            except PermissionError:
                output_path.write_bytes(temp_path.read_bytes())

            if not output_path.exists():
                raise RuntimeError("favorite handout pdf missing after finalize")
            if output_path.stat().st_size <= 0:
                raise RuntimeError("favorite handout pdf is empty")
            return output_path.stat().st_size
        except Exception:
            if output_path.exists():
                try:
                    output_path.unlink(missing_ok=True)
                except PermissionError:
                    LOGGER.warning(
                        "favorite handout output cleanup skipped | request_id=%s file=%s",
                        get_request_id(),
                        output_path.name,
                    )
            raise
        finally:
            for source_pdf in source_pdfs:
                try:
                    source_pdf.close()
                except Exception:
                    pass
            try:
                merged_pdf.close()
            except Exception:
                pass
            if temp_path.exists():
                try:
                    temp_path.unlink(missing_ok=True)
                except PermissionError:
                    LOGGER.debug(
                        "favorite handout temp cleanup deferred | request_id=%s file=%s",
                        get_request_id(),
                        temp_path.name,
                    )

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
        now = datetime.utcnow()
        return record.expires_at <= now
