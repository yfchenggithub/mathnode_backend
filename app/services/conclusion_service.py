from __future__ import annotations

import logging
from urllib.parse import quote

from app.core.exceptions import BizException
from app.core.request_context import get_request_id
from app.stores.interfaces import ContentStore, PdfMappingStore

LOGGER = logging.getLogger(__name__)


def _derive_pdf_meta(
    conclusion_id: str,
    pdf_mapping_store: PdfMappingStore,
) -> dict[str, str | bool | None]:
    pdf_filename = pdf_mapping_store.get_pdf_filename(conclusion_id)
    if not pdf_filename:
        LOGGER.debug(
            "conclusion pdf mapping missing | request_id=%s conclusion_id=%s",
            get_request_id(),
            conclusion_id,
        )
        return {
            "pdf_url": None,
            "pdf_filename": None,
            "pdf_available": False,
        }

    LOGGER.debug(
        "conclusion pdf mapping found | request_id=%s conclusion_id=%s pdf_filename=%s",
        get_request_id(),
        conclusion_id,
        pdf_filename,
    )
    return {
        "pdf_url": f"/api/v1/pdfs/{quote(pdf_filename)}",
        "pdf_filename": pdf_filename,
        "pdf_available": True,
    }


class ConclusionService:
    @staticmethod
    def get_by_id(
        content_store: ContentStore,
        pdf_mapping_store: PdfMappingStore,
        conclusion_id: str,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()
        LOGGER.info(
            "conclusion detail start | request_id=%s conclusion_id=%s favorite_count=%s",
            get_request_id(),
            conclusion_id,
            len(favorite_ids),
        )

        raw_row = content_store.get_raw_by_id(conclusion_id)
        if not raw_row:
            LOGGER.warning(
                "conclusion detail not found | request_id=%s conclusion_id=%s",
                get_request_id(),
                conclusion_id,
            )
            raise BizException(code=4040, message="结论不存在")

        response_data = dict(raw_row)
        raw_id = response_data.get("id")
        record_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else conclusion_id

        if record_id != conclusion_id:
            LOGGER.debug(
                "conclusion id remapped | request_id=%s requested_id=%s record_id=%s",
                get_request_id(),
                conclusion_id,
                record_id,
            )

        response_data["is_favorited"] = record_id in favorite_ids
        response_data.update(_derive_pdf_meta(record_id, pdf_mapping_store))

        LOGGER.info(
            (
                "conclusion detail success | request_id=%s conclusion_id=%s record_id=%s "
                "pdf_available=%s is_favorited=%s"
            ),
            get_request_id(),
            conclusion_id,
            record_id,
            response_data.get("pdf_available"),
            response_data.get("is_favorited"),
        )
        return response_data
