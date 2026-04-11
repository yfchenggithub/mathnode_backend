"""
文件作用：
- 提供 PDF 文件定位与安全校验能力，供 API 路由复用。

设计思路：
- 将路径解析、路径合法性校验、文件类型校验集中在 service 层。
- 路由层只负责 HTTP 协议行为（状态码、响应体、响应头），避免安全逻辑分散。

主要功能：
- 解析 PDF 根目录（支持相对路径与绝对路径，兼容 Windows/Linux）。
- 防止路径穿越与绝对路径逃逸。
- 限制只允许访问 .pdf/.PDF 文件。
- 返回可直接用于 FileResponse 的绝对路径与文件名。

为什么这样设计：
- 在 MVP 阶段遵循最小改动原则，不改变现有架构主干。
- 通过单点校验保证安全和可维护性，后续扩展下载鉴权或对象存储时可平滑演进。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PdfPathValidationError(ValueError):
    """PDF 请求路径非法。"""


class PdfFileNotFoundError(FileNotFoundError):
    """PDF 文件不存在。"""


@dataclass(frozen=True)
class PdfFile:
    absolute_path: Path
    filename: str


class PdfService:
    @staticmethod
    def resolve_pdf_root(raw_root_dir: str) -> Path:
        root_path = Path(raw_root_dir).expanduser()
        if not root_path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            root_path = project_root / root_path
        return root_path.resolve()

    @staticmethod
    def resolve_pdf_file(file_path: str, raw_root_dir: str) -> PdfFile:
        normalized_input = file_path.strip()
        if not normalized_input:
            raise PdfPathValidationError("文件路径不能为空")
        if "\x00" in normalized_input:
            raise PdfPathValidationError("文件路径包含非法字符")

        requested_path = Path(normalized_input)

        # 禁止绝对路径（含 Windows 盘符）直接访问。
        if requested_path.is_absolute() or requested_path.drive:
            raise PdfPathValidationError("不允许使用绝对路径访问文件")

        # 禁止目录穿越片段，避免通过 ../ 逃逸根目录。
        if any(part in {"..", "."} for part in requested_path.parts):
            raise PdfPathValidationError("文件路径不合法")

        if requested_path.suffix.lower() != ".pdf":
            raise PdfPathValidationError("仅支持访问 PDF 文件")

        root_path = PdfService.resolve_pdf_root(raw_root_dir)
        absolute_path = (root_path / requested_path).resolve()

        try:
            absolute_path.relative_to(root_path)
        except ValueError as exc:
            raise PdfPathValidationError("文件路径越界，禁止访问") from exc

        if not absolute_path.is_file():
            raise PdfFileNotFoundError("PDF 文件不存在")

        return PdfFile(
            absolute_path=absolute_path,
            filename=absolute_path.name,
        )
