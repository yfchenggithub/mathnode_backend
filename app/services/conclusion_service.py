from urllib.parse import quote

from app.core.exceptions import BizException
from app.stores.interfaces import ContentStore


def _derive_pdf_url(raw_record: dict[str, object]) -> str | None:
    assets = raw_record.get("assets")
    if not isinstance(assets, dict):
        return None

    raw_pdf = assets.get("pdf")
    if not isinstance(raw_pdf, str):
        return None

    pdf_name = raw_pdf.strip()
    if not pdf_name:
        return None

    if pdf_name.startswith(("http://", "https://", "/")):
        return pdf_name

    return f"/api/v1/pdfs/{quote(pdf_name)}"


class ConclusionService:
    @staticmethod
    def get_by_id(
        content_store: ContentStore,
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
        response_data["pdf_url"] = _derive_pdf_url(raw_row)
        return response_data
