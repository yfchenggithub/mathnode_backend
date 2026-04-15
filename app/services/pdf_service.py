from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class PdfPathValidationError(ValueError):
    """PDF request path is invalid."""


class PdfFileNotFoundError(FileNotFoundError):
    """PDF file does not exist."""


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
        resolved_root = root_path.resolve()
        LOGGER.debug("pdf root resolved | raw_root_dir=%s resolved=%s", raw_root_dir, resolved_root)
        return resolved_root

    @staticmethod
    def resolve_pdf_file(file_path: str, raw_root_dir: str) -> PdfFile:
        normalized_input = file_path.strip()
        LOGGER.debug("pdf resolve start | file_path=%s", normalized_input)

        if not normalized_input:
            raise PdfPathValidationError("文件路径不能为空")
        if "\x00" in normalized_input:
            raise PdfPathValidationError("文件路径包含非法字符")

        requested_path = Path(normalized_input)

        if requested_path.is_absolute() or requested_path.drive:
            raise PdfPathValidationError("文件路径不合法")

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

        LOGGER.debug(
            "pdf resolve success | file_path=%s absolute_path=%s",
            normalized_input,
            absolute_path,
        )
        return PdfFile(
            absolute_path=absolute_path,
            filename=absolute_path.name,
        )
