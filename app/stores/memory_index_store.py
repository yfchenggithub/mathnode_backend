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
from copy import deepcopy
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class MemoryIndexStore:
    _MODULE_LABEL_MAP = {
        "inequality": "不等式",
        "function": "函数",
        "trigonometry": "三角",
        "algebra": "代数",
        "geometry": "几何",
        "sequence": "数列",
        "probability": "概率统计",
        "analytic_geometry": "解析几何",
        "vector": "向量",
        "complex": "复数",
    }

    def __init__(self, records: list[dict[str, Any]], source: str = "content_store") -> None:
        self._source = source
        self._records: list[dict[str, Any]] = []

        for item in sorted(records, key=lambda x: x["id"]):
            doc_payload = self._build_doc_payload(item)
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
                "doc_payload": doc_payload,
            }
            normalized["_title_lower"] = normalized["title"].lower()
            normalized["_module_lower"] = normalized["module"].lower()
            normalized["_statement_clean_lower"] = normalized["statement_clean"].lower()
            normalized["_tags_text_lower"] = normalized["tags_text"].lower()
            self._records.append(normalized)

    @staticmethod
    def _build_doc_payload(item: dict[str, Any]) -> dict[str, Any]:
        raw_payload = item.get("doc_payload")
        if isinstance(raw_payload, dict):
            payload = deepcopy(raw_payload)
        else:
            # 兼容旧记录格式：若没有 doc_payload，则退回旧搜索字段。
            payload = {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "module": str(item.get("module", "")),
                "difficulty": int(item.get("difficulty", 1)),
                "tags": [str(x).strip() for x in item.get("tags", []) if str(x).strip()],
                "statement_clean": str(item.get("statement_clean", "")),
            }

        if not str(payload.get("id", "")).strip():
            payload["id"] = str(item.get("id", ""))

        return payload

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
        LOGGER.debug(
            (
                "memory index search matched | q=%r module=%s difficulty=%s tag=%s "
                "total=%s page=%s page_size=%s"
            ),
            q.strip(),
            module,
            difficulty,
            tag,
            total,
            page,
            page_size,
        )

        start = (page - 1) * page_size
        end = start + page_size
        page_rows = matched_rows[start:end]

        items: list[dict[str, Any]] = []
        for row in page_rows:
            item_payload = deepcopy(row["doc_payload"])
            item_payload["is_favorited"] = row["id"] in favorite_ids
            items.append(item_payload)

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

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        if value < low:
            return low
        if value > high:
            return high
        return value

    @classmethod
    def _module_label(cls, module: str) -> str:
        text = module.strip()
        if not text:
            return "其他"
        return cls._MODULE_LABEL_MAP.get(text.lower(), text)

    def _build_suggest_item(self, row: dict[str, Any], keyword: str) -> dict[str, Any]:
        keyword_lower = keyword.lower()
        match_type = "contains"
        match_field = "statement_clean"
        base_score = 0.70

        if row["_title_lower"] == keyword_lower:
            match_type = "exact"
            match_field = "title"
            base_score = 1.00
        elif row["_title_lower"].startswith(keyword_lower):
            match_type = "prefix"
            match_field = "title"
            base_score = 0.95
        elif keyword_lower in row["_title_lower"]:
            match_type = "contains"
            match_field = "title"
            base_score = 0.90
        elif keyword_lower in row["_tags_text_lower"]:
            match_type = "contains"
            match_field = "tags"
            base_score = 0.82
        elif keyword_lower in row["_module_lower"]:
            match_type = "contains"
            match_field = "module"
            base_score = 0.78
        elif keyword_lower in row["_statement_clean_lower"]:
            match_type = "contains"
            match_field = "statement_clean"
            base_score = 0.74

        doc_payload = row["doc_payload"]
        search_boost = self._clamp(self._safe_float(doc_payload.get("searchBoost")), 0.0, 1.0)
        hot_score = self._clamp(self._safe_float(doc_payload.get("hotScore")), 0.0, 100.0)
        exam_frequency = self._clamp(self._safe_float(doc_payload.get("examFrequency")), 0.0, 1.0)

        score = base_score
        score += search_boost * 0.03
        score += (hot_score / 100.0) * 0.03
        score += exam_frequency * 0.02
        score = round(self._clamp(score, 0.0, 1.0), 3)

        badge = ""
        if hot_score >= 85.0 or exam_frequency >= 1.0:
            badge = "高频"
        elif search_boost >= 0.9 or hot_score >= 70.0:
            badge = "常用"
        elif row["difficulty"] >= 4:
            badge = "进阶"

        module = row["module"] or "unknown"
        module_label = self._module_label(module)
        difficulty = row["difficulty"]
        return {
            "id": row["id"],
            "title": row["title"],
            "subtitle": f"{module_label} · 难度{difficulty}",
            "route": f"/conclusions/{row['id']}",
            "module": module,
            "difficulty": difficulty,
            "tags": row["tags"],
            "match_type": match_type,
            "match_field": match_field,
            "matched_text": keyword,
            "score": score,
            "badge": badge,
        }

    def suggest(self, q: str) -> dict[str, Any]:
        keyword = q.strip()
        if not keyword:
            return {
                "query": "",
                "total": 0,
                "empty_hint": "请输入关键词",
                "items": [],
            }

        rows = self._filter_records(
            q=keyword,
            module=None,
            difficulty=None,
            tag=None,
        )
        LOGGER.debug(
            "memory index suggest matched | q=%r total=%s",
            keyword,
            len(rows),
        )
        limited_items = [
            self._build_suggest_item(row=row, keyword=keyword)
            for row in rows[:8]
        ]
        LOGGER.debug(
            "memory index suggest truncated | q=%r returned=%s limit=%s",
            keyword,
            len(limited_items),
            8,
        )

        return {
            "query": keyword,
            "total": len(rows),
            "empty_hint": "" if limited_items else "没有匹配结果，换个关键词试试",
            "items": limited_items,
        }

    def count(self) -> int:
        return len(self._records)

    def stats(self) -> dict[str, Any]:
        return {
            "store": self.__class__.__name__,
            "source": self._source,
            "count": len(self._records),
        }
