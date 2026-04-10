"""
用途：
- 启动期从 content 文档构建 search 索引文档
职责：
- 抽取搜索所需字段并统计索引关键字段质量
设计：
- index loader 与 content loader 解耦，后续可替换为外部索引源
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.stores.interfaces import ContentDocument


@dataclass
class IndexLoadResult:
    records: list[dict[str, Any]]
    source: str
    missing_key_field_count: int


def build_index_records_from_content(
    content_records: Sequence[ContentDocument],
) -> IndexLoadResult:
    records: list[dict[str, Any]] = []
    missing_key_field_count = 0

    for doc in content_records:
        if not str(doc.get("id", "")).strip():
            missing_key_field_count += 1
        if not str(doc.get("title", "")).strip():
            missing_key_field_count += 1
        if not str(doc.get("module", "")).strip():
            missing_key_field_count += 1
        if not str(doc.get("statement_clean", "")).strip():
            missing_key_field_count += 1

        records.append(
            {
                "id": str(doc.get("id", "")),
                "title": str(doc.get("title", "")),
                "module": str(doc.get("module", "")),
                "difficulty": int(doc.get("difficulty", 1)),
                "tags": list(doc.get("tags", [])),
                "statement_clean": str(doc.get("statement_clean", "")),
            }
        )

    return IndexLoadResult(
        records=records,
        source="content_store:memory",
        missing_key_field_count=missing_key_field_count,
    )
