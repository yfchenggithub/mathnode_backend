"""
用途：
- 启动期从 SQLite 读取全部 Conclusion
职责：
- 将 ORM 数据标准化为 ContentStore 可直接使用的内存文档
- 统计导入质量指标（重复 id、关键字段缺失）
设计：
- loader 只负责数据读取与转换，不负责请求期查询
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.conclusion_repo import ConclusionRepository
from app.stores.interfaces import ContentDocument

LOGGER = logging.getLogger(__name__)


@dataclass
class ContentLoadResult:
    records: list[ContentDocument]
    source: str
    total_rows: int
    duplicate_id_count: int
    missing_key_field_count: int


def _split_tags(tags_text: str | None) -> list[str]:
    if not tags_text:
        return []
    return [x.strip() for x in tags_text.split(",") if x.strip()]


def _parse_json_list(raw_value: str | None, field_name: str, conclusion_id: str) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        LOGGER.warning(
            "Invalid JSON in conclusions.%s, conclusion_id=%s",
            field_name,
            conclusion_id,
        )
        return []

    if not isinstance(parsed, list):
        LOGGER.warning(
            "JSON field is not list in conclusions.%s, conclusion_id=%s",
            field_name,
            conclusion_id,
        )
        return []

    return [str(x) for x in parsed]


def load_content_from_sqlite(db: Session) -> ContentLoadResult:
    rows = ConclusionRepository.list_all(db)

    records: list[ContentDocument] = []
    seen_ids: set[str] = set()
    duplicate_id_count = 0
    missing_key_field_count = 0

    for row in rows:
        conclusion_id = str(row.id)

        if conclusion_id in seen_ids:
            duplicate_id_count += 1
            continue
        seen_ids.add(conclusion_id)

        if not str(row.title or "").strip():
            missing_key_field_count += 1
        if not str(row.module or "").strip():
            missing_key_field_count += 1
        if not str(row.statement_clean or "").strip():
            missing_key_field_count += 1

        records.append(
            {
                "id": conclusion_id,
                "title": str(row.title or ""),
                "module": str(row.module or ""),
                "difficulty": int(row.difficulty or 1),
                "tags": _split_tags(row.tags),
                "statement_clean": str(row.statement_clean or ""),
                "statement": str(row.statement or ""),
                "explanation": str(row.explanation or ""),
                "proof": str(row.proof or ""),
                "examples": _parse_json_list(row.examples_json, "examples_json", conclusion_id),
                "traps": _parse_json_list(row.traps_json, "traps_json", conclusion_id),
                "summary": str(row.summary or ""),
                "pdf_url": row.pdf_url,
            }
        )

    return ContentLoadResult(
        records=records,
        source="sqlite:conclusions",
        total_rows=len(rows),
        duplicate_id_count=duplicate_id_count,
        missing_key_field_count=missing_key_field_count,
    )
