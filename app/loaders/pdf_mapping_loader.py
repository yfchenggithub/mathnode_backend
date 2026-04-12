from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.services.pdf_service import PdfFileNotFoundError, PdfPathValidationError, PdfService

LOGGER = logging.getLogger(__name__)

DEFAULT_CONCLUSION_PDF_MAP_PATH = Path("app/data/conclusion_pdf_map.json")


@dataclass
class PdfMappingLoadResult:
    mapping: dict[str, str]
    source: str
    total_rows: int
    valid_rows: int
    invalid_row_count: int
    duplicate_id_count: int


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _resolve_mapping_json_path(mapping_json_path: str | Path) -> Path:
    path = Path(mapping_json_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    return path


def _load_mapping_root(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"PDF mapping JSON file not found: {path}")
    if not path.is_file():
        raise RuntimeError(f"PDF mapping JSON path is not a file: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        LOGGER.exception("Failed to read PDF mapping JSON file: %s", path)
        raise RuntimeError(f"Failed to read PDF mapping JSON file: {path}") from exc

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        LOGGER.exception("Invalid JSON format in PDF mapping file: %s", path)
        raise ValueError(f"Invalid JSON format in PDF mapping file: {path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "PDF mapping JSON top-level value must be an object/dict, "
            f"got: {type(parsed).__name__}"
        )

    normalized: dict[str, object] = {}
    for raw_key, raw_value in parsed.items():
        normalized[str(raw_key)] = raw_value
    return normalized


def load_pdf_mapping(
    mapping_json_path: str | Path = DEFAULT_CONCLUSION_PDF_MAP_PATH,
    *,
    pdf_root_dir: str,
    strict: bool = False,
) -> PdfMappingLoadResult:
    path = _resolve_mapping_json_path(mapping_json_path)
    mapping_root = _load_mapping_root(path)

    mapping: dict[str, str] = {}
    invalid_row_count = 0
    duplicate_id_count = 0

    for raw_conclusion_id, raw_filename in mapping_root.items():
        conclusion_id = _safe_str(raw_conclusion_id).strip()
        pdf_filename = _safe_str(raw_filename).strip()

        if not conclusion_id or not pdf_filename:
            invalid_row_count += 1
            message = (
                f"Invalid PDF mapping row: conclusion_id='{raw_conclusion_id}' "
                f"pdf_filename='{raw_filename}'"
            )
            if strict:
                raise ValueError(message)
            LOGGER.warning("%s (skipped)", message)
            continue

        try:
            PdfService.resolve_pdf_file(file_path=pdf_filename, raw_root_dir=pdf_root_dir)
        except (PdfPathValidationError, PdfFileNotFoundError) as exc:
            invalid_row_count += 1
            message = (
                f"Invalid PDF mapping row: conclusion_id='{conclusion_id}' "
                f"pdf_filename='{pdf_filename}' reason='{exc}'"
            )
            if strict:
                raise ValueError(message) from exc
            LOGGER.warning("%s (skipped)", message)
            continue

        if conclusion_id in mapping:
            duplicate_id_count += 1
            LOGGER.warning("Duplicate PDF mapping id detected and overwritten: id=%s", conclusion_id)

        mapping[conclusion_id] = pdf_filename

    result = PdfMappingLoadResult(
        mapping=mapping,
        source=f"json:{path.as_posix()}",
        total_rows=len(mapping_root),
        valid_rows=len(mapping),
        invalid_row_count=invalid_row_count,
        duplicate_id_count=duplicate_id_count,
    )

    LOGGER.info(
        (
            "PDF mapping loaded from JSON: path=%s total_rows=%s valid_rows=%s "
            "invalid_row_count=%s duplicate_id_count=%s"
        ),
        path,
        result.total_rows,
        result.valid_rows,
        result.invalid_row_count,
        result.duplicate_id_count,
    )
    return result
