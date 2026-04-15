from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.request_context import get_request_id
from app.core.response import error_response
from app.services.pdf_service import (
    PdfFileNotFoundError,
    PdfPathValidationError,
    PdfService,
)

router = APIRouter()
LOGGER = logging.getLogger(__name__)

PDF_BAD_REQUEST_CODE = 4001
PDF_NOT_FOUND_CODE = 4040


def _json_error(status_code: int, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code=code, message=message),
    )


@router.get(
    "/pdfs/{file_path:path}",
    response_class=FileResponse,
    summary="预览或下载 PDF 文件",
    responses={
        200: {
            "description": "返回 PDF 文件流",
            "content": {"application/pdf": {}},
        },
        400: {
            "description": "请求参数或文件路径非法",
            "content": {
                "application/json": {
                    "example": error_response(code=PDF_BAD_REQUEST_CODE, message="文件路径不合法")
                }
            },
        },
        404: {
            "description": "PDF 文件不存在",
            "content": {
                "application/json": {
                    "example": error_response(code=PDF_NOT_FOUND_CODE, message="PDF 文件不存在")
                }
            },
        },
    },
)
def get_pdf(
    file_path: str,
    download: bool = Query(default=False, description="是否下载，1/true 表示下载"),
):
    LOGGER.info(
        "pdf request received | request_id=%s file_path=%s download=%s root_dir=%s",
        get_request_id(),
        file_path,
        str(download).lower(),
        settings.PDF_ROOT_DIR,
    )

    try:
        pdf_file = PdfService.resolve_pdf_file(
            file_path=file_path,
            raw_root_dir=settings.PDF_ROOT_DIR,
        )
    except PdfPathValidationError as exc:
        LOGGER.warning(
            "pdf request invalid path | request_id=%s file_path=%s reason=%s",
            get_request_id(),
            file_path,
            str(exc),
        )
        return _json_error(status_code=400, code=PDF_BAD_REQUEST_CODE, message=str(exc))
    except PdfFileNotFoundError as exc:
        LOGGER.warning(
            "pdf request file not found | request_id=%s file_path=%s reason=%s",
            get_request_id(),
            file_path,
            str(exc),
        )
        return _json_error(status_code=404, code=PDF_NOT_FOUND_CODE, message=str(exc))

    content_disposition_type = "attachment" if download else "inline"
    LOGGER.info(
        (
            "pdf request success | request_id=%s file_path=%s absolute_path=%s "
            "disposition=%s"
        ),
        get_request_id(),
        file_path,
        pdf_file.absolute_path,
        content_disposition_type,
    )

    return FileResponse(
        path=str(pdf_file.absolute_path),
        media_type="application/pdf",
        filename=pdf_file.filename,
        content_disposition_type=content_disposition_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
