"""
用途：
- 内存版 content store
职责：
- 请求期按 id 读取结论详情
- 提供存在性校验与轻量摘要读取
设计：
- 启动期一次性装载，运行期只读
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.stores.interfaces import ContentDocument, ContentRawRecord, ContentSummary


class MemoryContentStore:
    def __init__(
        self,
        documents: list[ContentDocument],
        source: str = "content_loader",
        raw_records_by_id: dict[str, ContentRawRecord] | None = None,
    ) -> None:
        self._source = source
        self._by_id: dict[str, ContentDocument] = {
            doc["id"]: self._clone_document(doc) for doc in documents
        }
        if raw_records_by_id is not None:
            self._raw_by_id: dict[str, ContentRawRecord] = {
                conclusion_id: self._clone_raw_record(raw_record)
                for conclusion_id, raw_record in raw_records_by_id.items()
            }
        else:
            self._raw_by_id = {
                doc["id"]: self._build_default_raw_record(doc) for doc in documents
            }

    @staticmethod
    def _clone_document(doc: ContentDocument) -> ContentDocument:
        return {
            "id": doc["id"],
            "title": doc["title"],
            "module": doc["module"],
            "difficulty": doc["difficulty"],
            "tags": list(doc["tags"]),
            "statement_clean": doc["statement_clean"],
            "statement": doc["statement"],
            "explanation": doc["explanation"],
            "proof": doc["proof"],
            "examples": list(doc["examples"]),
            "traps": list(doc["traps"]),
            "summary": doc["summary"],
            "pdf_url": doc["pdf_url"],
        }

    @staticmethod
    def _clone_raw_record(raw_record: ContentRawRecord) -> ContentRawRecord:
        return deepcopy(raw_record)

    @staticmethod
    def _build_default_raw_record(doc: ContentDocument) -> ContentRawRecord:
        return {
            "id": doc["id"],
            "title": doc["title"],
            "module": doc["module"],
            "difficulty": doc["difficulty"],
            "tags": list(doc["tags"]),
            "statement_clean": doc["statement_clean"],
            "statement": doc["statement"],
            "explanation": doc["explanation"],
            "proof": doc["proof"],
            "examples": list(doc["examples"]),
            "traps": list(doc["traps"]),
            "summary": doc["summary"],
            "pdf_url": doc["pdf_url"],
        }

    def get_by_id(self, conclusion_id: str) -> ContentDocument | None:
        doc = self._by_id.get(conclusion_id)
        if doc is None:
            return None
        return self._clone_document(doc)

    def get_raw_by_id(self, conclusion_id: str) -> ContentRawRecord | None:
        raw_record = self._raw_by_id.get(conclusion_id)
        if raw_record is None:
            return None
        return self._clone_raw_record(raw_record)

    def exists(self, conclusion_id: str) -> bool:
        return conclusion_id in self._by_id

    def get_summary(self, conclusion_id: str) -> ContentSummary | None:
        doc = self._by_id.get(conclusion_id)
        if doc is None:
            return None
        return {
            "id": doc["id"],
            "title": doc["title"],
            "module": doc["module"],
        }

    def count(self) -> int:
        return len(self._by_id)

    def stats(self) -> dict[str, Any]:
        return {
            "store": self.__class__.__name__,
            "source": self._source,
            "count": len(self._by_id),
        }
