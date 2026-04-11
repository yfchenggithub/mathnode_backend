"""
文件作用：
- 提供 PDF 文件 HTTP GET 访问接口，支持浏览器预览与下载。

设计思路：
- 路由层专注于协议行为：解析查询参数、返回 FileResponse、构造统一 JSON 错误。
- 路径与安全相关逻辑统一放在 PdfService，避免重复实现和遗漏校验。

主要功能：
- GET /pdfs/{file_path:path}：默认 inline 预览。
- GET /pdfs/{file_path:path}?download=1：attachment 下载。
- 返回 application/pdf，并兼容中文文件名。

为什么这样设计：
- 贴合项目现有 api/v1 路由组织方式，改动面最小。
- 保持接口行为清晰，便于后续扩展鉴权、审计日志、限流等能力。
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.response import error_response
from app.services.pdf_service import (
    PdfFileNotFoundError,
    PdfPathValidationError,
    PdfService,
)

router = APIRouter()

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
    download: bool = Query(default=False, description="是否下载：1/true 表示下载"),
):
    try:
        pdf_file = PdfService.resolve_pdf_file(
            file_path=file_path,
            raw_root_dir=settings.PDF_ROOT_DIR,
        )
    except PdfPathValidationError as exc:
        return _json_error(status_code=400, code=PDF_BAD_REQUEST_CODE, message=str(exc))
    except PdfFileNotFoundError as exc:
        return _json_error(status_code=404, code=PDF_NOT_FOUND_CODE, message=str(exc))

    content_disposition_type = "attachment" if download else "inline"

    return FileResponse(
        path=str(pdf_file.absolute_path),
        media_type="application/pdf",
        filename=pdf_file.filename,
        content_disposition_type=content_disposition_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
