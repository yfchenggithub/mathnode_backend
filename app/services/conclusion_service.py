from urllib.parse import quote

from app.core.exceptions import BizException
from app.stores.interfaces import ContentStore, PdfMappingStore


def _derive_pdf_meta(
    conclusion_id: str,
    pdf_mapping_store: PdfMappingStore,
) -> dict[str, str | bool | None]:
    pdf_filename = pdf_mapping_store.get_pdf_filename(conclusion_id)
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


class ConclusionService:
    @staticmethod
    def get_by_id(
        content_store: ContentStore,
        pdf_mapping_store: PdfMappingStore,
        conclusion_id: str,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()

        raw_row = content_store.get_raw_by_id(conclusion_id)
        if not raw_row:
            raise BizException(code=4040, message="结论不存在")

        response_data = dict(raw_row)
        raw_id = response_data.get("id")
        record_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else conclusion_id

        response_data["is_favorited"] = record_id in favorite_ids
        response_data.update(_derive_pdf_meta(record_id, pdf_mapping_store))
        return response_data
