from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.models.correction_report import CorrectionReport
from app.repositories.correction_report_repo import CorrectionReportRepository
from app.schemas.correction_report import CorrectionReportCreateRequest

LOGGER = logging.getLogger(__name__)

VALID_LOCATIONS: set[str] = {
    "title",
    "summary",
    "core_formula",
    "body",
    "pdf",
    "other",
}
VALID_TYPES: set[str] = {"formula", "text", "layout", "other"}
VALID_STATUSES: set[str] = {"pending", "reviewed", "ignored"}


def _mask_optional_user_id(user_id: str | None) -> str:
    if not user_id:
        return "anonymous"
    return mask_sensitive(user_id, left=2, right=2)


class CorrectionReportService:
    @staticmethod
    def _normalize_text(value: str | None, max_length: int) -> str:
        text = (value or "").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length]

    @staticmethod
    def _normalize_choice(
        value: str | None,
        *,
        valid_values: set[str],
        fallback: str,
        error_message: str,
    ) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            return fallback
        if normalized not in valid_values:
            raise BizException(
                code=4232,
                message=error_message,
                status_code=422,
            )
        return normalized

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        normalized = (status or "").strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_STATUSES:
            raise BizException(
                code=4233,
                message="invalid correction report status",
                status_code=422,
            )
        return normalized

    @staticmethod
    def serialize(row: CorrectionReport) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "conclusion_id": row.conclusion_id,
            "conclusion_title": row.conclusion_title,
            "error_location": row.error_location,
            "error_type": row.error_type,
            "description": row.description,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    @staticmethod
    def create_report(
        db: Session,
        *,
        user_id: str | None,
        payload: CorrectionReportCreateRequest,
    ) -> dict:
        conclusion_id = CorrectionReportService._normalize_text(
            payload.conclusion_id,
            32,
        )
        conclusion_title = CorrectionReportService._normalize_text(
            payload.conclusion_title,
            160,
        )
        description = CorrectionReportService._normalize_text(
            payload.description,
            200,
        )

        if not conclusion_id or not conclusion_title or not description:
            LOGGER.warning(
                (
                    "correction report rejected | request_id=%s user_id=%s "
                    "conclusion_id=%r reason=missing_required"
                ),
                get_request_id(),
                _mask_optional_user_id(user_id),
                conclusion_id,
            )
            raise BizException(
                code=4231,
                message="correction report content is required",
                status_code=422,
            )

        values = {
            "user_id": user_id,
            "conclusion_id": conclusion_id,
            "conclusion_title": conclusion_title,
            "error_location": CorrectionReportService._normalize_choice(
                payload.error_location,
                valid_values=VALID_LOCATIONS,
                fallback="body",
                error_message="invalid correction report location",
            ),
            "error_type": CorrectionReportService._normalize_choice(
                payload.error_type,
                valid_values=VALID_TYPES,
                fallback="text",
                error_message="invalid correction report type",
            ),
            "description": description,
            "status": "pending",
        }

        row = CorrectionReportRepository.create(db, values)
        LOGGER.info(
            (
                "correction report created | request_id=%s user_id=%s id=%s "
                "conclusion_id=%s title=%r"
            ),
            get_request_id(),
            _mask_optional_user_id(user_id),
            row.id,
            row.conclusion_id,
            summarize_text(row.conclusion_title, max_length=80),
        )
        return CorrectionReportService.serialize(row)

    @staticmethod
    def list_reports(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_status = CorrectionReportService._normalize_status(status)
        rows, total = CorrectionReportRepository.list_reports(
            db,
            status=normalized_status,
            keyword=CorrectionReportService._normalize_text(keyword, 80),
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [CorrectionReportService.serialize(row) for row in rows],
        }
