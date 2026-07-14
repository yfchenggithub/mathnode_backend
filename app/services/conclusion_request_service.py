from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BizException, NotFoundError
from app.core.logging_helpers import mask_sensitive, summarize_text
from app.core.request_context import get_request_id
from app.models.conclusion_request import ConclusionRequest
from app.repositories.conclusion_request_repo import ConclusionRequestRepository
from app.schemas.conclusion_request import (
    ConclusionRequestCreateRequest,
    ConclusionRequestStatus,
)

LOGGER = logging.getLogger(__name__)

VALID_STATUSES: set[str] = {"pending", "updated", "ignored"}


def _mask_optional_user_id(user_id: str | None) -> str:
    if not user_id:
        return "anonymous"
    return mask_sensitive(user_id, left=2, right=2)


class ConclusionRequestService:
    @staticmethod
    def _normalize_text(value: str | None, max_length: int) -> str:
        text = (value or "").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length]

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        normalized = (status or "").strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_STATUSES:
            raise BizException(
                code=4222,
                message="invalid conclusion request status",
                status_code=422,
            )
        return normalized

    @staticmethod
    def serialize(row: ConclusionRequest) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "query": row.query,
            "note": row.note,
            "source": row.source,
            "page": row.page,
            "entry": row.entry,
            "active_tab": row.active_tab,
            "result_count": row.result_count,
            "has_result": row.has_result,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    @staticmethod
    def create_request(
        db: Session,
        *,
        user_id: str | None,
        payload: ConclusionRequestCreateRequest,
    ) -> dict:
        query = ConclusionRequestService._normalize_text(payload.query, 40)
        note = ConclusionRequestService._normalize_text(payload.note, 100)

        if not query and not note:
            LOGGER.warning(
                "conclusion request rejected | request_id=%s user_id=%s reason=empty",
                get_request_id(),
                _mask_optional_user_id(user_id),
            )
            raise BizException(
                code=4221,
                message="conclusion request content is required",
                status_code=422,
            )

        values = {
            "user_id": user_id,
            "query": query,
            "note": note,
            "source": ConclusionRequestService._normalize_text(payload.source, 64) or "home",
            "page": ConclusionRequestService._normalize_text(payload.page, 64) or "home",
            "entry": (
                ConclusionRequestService._normalize_text(payload.entry, 64)
                or "search_hint"
            ),
            "active_tab": ConclusionRequestService._normalize_text(
                payload.active_tab,
                64,
            ),
            "result_count": max(0, int(payload.result_count or 0)),
            "has_result": bool(payload.has_result),
            "status": "pending",
        }

        row = ConclusionRequestRepository.create(db, values)
        LOGGER.info(
            "conclusion request created | request_id=%s user_id=%s id=%s query=%r",
            get_request_id(),
            _mask_optional_user_id(user_id),
            row.id,
            summarize_text(row.query, max_length=80),
        )
        return ConclusionRequestService.serialize(row)

    @staticmethod
    def list_requests(
        db: Session,
        *,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        normalized_status = ConclusionRequestService._normalize_status(status)
        rows, total = ConclusionRequestRepository.list_requests(
            db,
            status=normalized_status,
            keyword=ConclusionRequestService._normalize_text(keyword, 80),
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [ConclusionRequestService.serialize(row) for row in rows],
        }

    @staticmethod
    def update_status(
        db: Session,
        *,
        request_id: int,
        status: ConclusionRequestStatus,
    ) -> dict:
        normalized_status = ConclusionRequestService._normalize_status(status)
        if normalized_status is None:
            raise BizException(
                code=4222,
                message="invalid conclusion request status",
                status_code=422,
            )

        row = ConclusionRequestRepository.get_by_id(db, request_id)
        if row is None:
            raise NotFoundError(message="conclusion request not found")

        updated = ConclusionRequestRepository.update_status(db, row, normalized_status)
        return ConclusionRequestService.serialize(updated)
