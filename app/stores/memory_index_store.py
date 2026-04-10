"""
用途：
- 内存版搜索索引 store
职责：
- 请求期完成 search/suggest
- 维持与当前 API 契约一致的返回结构
设计：
- 启动期构建标准化索引字段，运行期只做内存过滤与分页
"""

from __future__ import annotations

from collections import Counter
from typing import Any


class MemoryIndexStore:
    def __init__(self, records: list[dict[str, Any]], source: str = "content_store") -> None:
        self._source = source
        self._records: list[dict[str, Any]] = []

        for item in sorted(records, key=lambda x: x["id"]):
            tags: list[str] = [str(x).strip() for x in item.get("tags", []) if str(x).strip()]
            tags_text = ",".join(tags)
            normalized = {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "module": str(item.get("module", "")),
                "difficulty": int(item.get("difficulty", 1)),
                "tags": tags,
                "tags_text": tags_text,
                "statement_clean": str(item.get("statement_clean", "")),
            }
            normalized["_title_lower"] = normalized["title"].lower()
            normalized["_module_lower"] = normalized["module"].lower()
            normalized["_statement_clean_lower"] = normalized["statement_clean"].lower()
            normalized["_tags_text_lower"] = normalized["tags_text"].lower()
            self._records.append(normalized)

    def _filter_records(
        self,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
    ) -> list[dict[str, Any]]:
        keyword = q.strip().lower()
        tag_keyword = (tag or "").strip().lower()

        rows: list[dict[str, Any]] = []
        for row in self._records:
            if module and row["module"] != module:
                continue

            if difficulty is not None and row["difficulty"] != difficulty:
                continue

            if tag_keyword and tag_keyword not in row["_tags_text_lower"]:
                continue

            if keyword:
                in_any_field = (
                    keyword in row["_title_lower"]
                    or keyword in row["_module_lower"]
                    or keyword in row["_statement_clean_lower"]
                    or keyword in row["_tags_text_lower"]
                )
                if not in_any_field:
                    continue

            rows.append(row)

        return rows

    def search(
        self,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None,
    ) -> dict[str, Any]:
        favorite_ids = favorite_ids or set()

        matched_rows = self._filter_records(
            q=q,
            module=module,
            difficulty=difficulty,
            tag=tag,
        )
        total = len(matched_rows)

        start = (page - 1) * page_size
        end = start + page_size
        page_rows = matched_rows[start:end]

        items = [
            {
                "id": row["id"],
                "title": row["title"],
                "module": row["module"],
                "difficulty": row["difficulty"],
                "tags": list(row["tags"]),
                "statement_clean": row["statement_clean"],
                "is_favorited": row["id"] in favorite_ids,
            }
            for row in page_rows
        ]

        module_counter = Counter(row["module"] for row in matched_rows)
        difficulty_counter = Counter(row["difficulty"] for row in matched_rows)
        tags_counter = Counter(
            tag_name
            for row in matched_rows
            for tag_name in row["tags"]
            if tag_name
        )

        return {
            "query": q,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "facets": {
                "module": [
                    {"value": key, "count": value}
                    for key, value in module_counter.items()
                ],
                "difficulty": [
                    {"value": key, "count": value}
                    for key, value in difficulty_counter.items()
                ],
                "tags": [
                    {"value": key, "count": value}
                    for key, value in tags_counter.items()
                ],
            },
        }

    def suggest(self, q: str) -> dict[str, Any]:
        keyword = q.strip()
        if not keyword:
            return {"items": []}

        rows = self._filter_records(
            q=keyword,
            module=None,
            difficulty=None,
            tag=None,
        )
        return {"items": [row["title"] for row in rows[:8]]}

    def count(self) -> int:
        return len(self._records)

    def stats(self) -> dict[str, Any]:
        return {
            "store": self.__class__.__name__,
            "source": self._source,
            "count": len(self._records),
        }
