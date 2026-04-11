"""
用途：
- 启动期加载后端离线检索索引文件（backend_search_index.json）。
职责：
- 负责索引文件读取、结构校验、字段转换与关键字段缺失统计。
- 对外返回稳定的 IndexLoadResult，供内存 IndexStore 初始化使用。
设计说明：
- 与 content loader 解耦，避免“内容数据源”和“检索索引数据源”强耦合。
- 保留历史函数名兼容层，确保下游调用可平滑迁移。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_INDEX_JSON_PATH = Path("app/data/backend_search_index.json")


@dataclass
class IndexLoadResult:
    records: list[dict[str, Any]]
    source: str
    missing_key_field_count: int


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _safe_tags(value: object) -> list[str]:
    """
    将 tags 规范为 list[str]。

    兼容策略：
    - list / tuple / set：逐项转字符串并去空。
    - str：支持按逗号/分号/竖线切分。
    - 其他类型：返回空列表，避免异常影响启动。
    """
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parts = [x.strip() for x in re.split(r"[，,;；|]+", text) if x.strip()]
        return parts

    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            text = _safe_str(item).strip()
            if text:
                result.append(text)
        return result

    return []


def _safe_int(value: object, default: int) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)

        text = _safe_str(value).strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)

        text = _safe_str(value).strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def _resolve_index_json_path(index_file_path: str | Path) -> Path:
    path = Path(index_file_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    return path


def _load_index_root(path: Path) -> dict[str, object]:
    """
    读取并解析索引 JSON 根对象。

    出错时抛出可读异常，方便 FastAPI 启动期快速定位。
    """
    if not path.exists():
        raise FileNotFoundError(f"Index JSON file not found: {path}")
    if not path.is_file():
        raise RuntimeError(f"Index JSON path is not a file: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        LOGGER.exception("Failed to read index JSON file: %s", path)
        raise RuntimeError(f"Failed to read index JSON file: {path}") from exc

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        LOGGER.exception("Invalid JSON format in index file: %s", path)
        raise ValueError(f"Invalid JSON format in index file: {path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "Index JSON top-level value must be an object/dict, "
            f"got: {type(parsed).__name__}"
        )
    return parsed


def _extract_docs_node(index_root: dict[str, object], path: Path) -> dict[str, dict[str, object]]:
    docs = index_root.get("docs")
    if docs is None:
        raise ValueError(f"Index JSON missing required 'docs' node: {path}")
    if not isinstance(docs, dict):
        raise ValueError(
            "Index JSON 'docs' node must be an object/dict, "
            f"got: {type(docs).__name__}"
        )

    normalized_docs: dict[str, dict[str, object]] = {}
    for raw_key, raw_doc in docs.items():
        key = _safe_str(raw_key).strip()
        if not key:
            raise ValueError("Index JSON docs contains empty key")
        if not isinstance(raw_doc, dict):
            raise ValueError(
                f"Index JSON docs['{key}'] must be an object/dict, "
                f"got: {type(raw_doc).__name__}"
            )
        normalized_docs[key] = raw_doc
    return normalized_docs


def _count_missing_fields(
    raw_id: str,
    title: str,
    module: str,
    statement_clean: str,
) -> int:
    """
    统计关键字段缺失数量。

    统计口径：
    - 字段缺失、None、空字符串（含仅空白）均计为缺失。
    - 当前关键字段为 id/title/module/statement_clean（兼容 summary）。
    """
    missing = 0
    for value in (raw_id, title, module, statement_clean):
        if not _safe_str(value).strip():
            missing += 1
    return missing


def _convert_doc_to_record(doc_key: str, doc: dict[str, object]) -> tuple[dict[str, Any], int]:
    """
    将 docs 节点中的单条文档转换为搜索记录。

    为什么这样做：
    - 输出字段尽量保持旧接口兼容（例如 statement_clean）。
    - 同时保留更多检索信号字段，便于后续排序/过滤扩展。
    """
    raw_id = _safe_str(doc.get("id")).strip()
    title = _safe_str(doc.get("title")).strip()
    module = _safe_str(doc.get("module")).strip()

    summary = _safe_str(doc.get("summary")).strip()
    # 兼容旧下游字段：新版索引没有 statement_clean 时，回退为 summary。
    statement_clean = summary or ""

    # 为保证下游索引记录可排序与查询，id 为空时使用 docs key 兜底。
    record_id = raw_id or doc_key

    record: dict[str, Any] = {
        "id": record_id,
        "title": title,
        "module": module,
        "difficulty": _safe_int(doc.get("difficulty"), default=1),
        "tags": _safe_tags(doc.get("tags")),
        "module_dir": _safe_str(doc.get("moduleDir")).strip(),
        "summary": summary,
        "statement_clean": statement_clean,
        "category": _safe_str(doc.get("category")).strip(),
        "core_formula": _safe_str(doc.get("coreFormula")).strip(),
        "rank": _safe_int(doc.get("rank"), default=0),
        "search_boost": _safe_float(doc.get("searchBoost"), default=0.0),
        "hot_score": _safe_float(doc.get("hotScore"), default=0.0),
        "exam_frequency": _safe_float(doc.get("examFrequency"), default=0.0),
        "exam_score": _safe_float(doc.get("examScore"), default=0.0),
    }

    missing_count = _count_missing_fields(
        raw_id=raw_id,
        title=title,
        module=module,
        statement_clean=statement_clean,
    )
    return record, missing_count


def load_index_records(
    index_file_path: str | Path = DEFAULT_INDEX_JSON_PATH,
) -> IndexLoadResult:
    """
    从离线索引 JSON 文件读取 docs，并转换为 IndexStore 可消费记录。

    输入：
    - index_file_path: 索引文件路径，支持相对/绝对路径。
    输出：
    - IndexLoadResult(records/source/missing_key_field_count)。
    """
    path = _resolve_index_json_path(index_file_path)
    index_root = _load_index_root(path)
    docs = _extract_docs_node(index_root=index_root, path=path)

    records: list[dict[str, Any]] = []
    missing_key_field_count = 0
    for doc_key, doc in docs.items():
        record, missing_count = _convert_doc_to_record(doc_key=doc_key, doc=doc)
        records.append(record)
        missing_key_field_count += missing_count

    result = IndexLoadResult(
        records=records,
        source="backend_search_index:file",
        missing_key_field_count=missing_key_field_count,
    )

    LOGGER.info(
        (
            "Index records loaded from JSON: path=%s docs=%s records=%s "
            "missing_key_field_count=%s"
        ),
        path,
        len(docs),
        len(result.records),
        result.missing_key_field_count,
    )
    return result


def load_index_records_from_file(
    index_file_path: str | Path = DEFAULT_INDEX_JSON_PATH,
) -> IndexLoadResult:
    """兼容命名别名：语义上等同于 load_index_records。"""
    return load_index_records(index_file_path=index_file_path)


def build_index_records_from_content(
    content_records: Sequence[object] | None = None,
    *,
    index_file_path: str | Path = DEFAULT_INDEX_JSON_PATH,
) -> IndexLoadResult:
    """
    历史兼容入口（保留函数名，避免下游一次性改造）。

    说明：
    - 旧版本从 content_records 构建索引。
    - 新版本改为统一从离线索引文件加载，content_records 参数不再参与构建。
    """
    if content_records is not None:
        LOGGER.warning(
            "build_index_records_from_content is deprecated; "
            "content_records is ignored and index is loaded from JSON file."
        )
    return load_index_records(index_file_path=index_file_path)
