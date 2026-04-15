"""
用途：
- 启动期从 canonical_content_v2.json 读取全部结论内容。
职责：
- 将 canonical v2 富结构内容降级映射为当前 ContentStore 可直接消费的扁平 ContentDocument。
- 统计导入质量指标（重复 id、关键字段缺失）。
设计：
- loader 只负责“读取 + 转换 + 基础校验”，不负责请求期查询。
- 保留历史函数名兼容层，避免调用方一次性大改。
"""

from __future__ import annotations

import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.stores.interfaces import ContentDocument, ContentRawRecord

LOGGER = logging.getLogger(__name__)

DEFAULT_CONTENT_JSON_PATH = Path("app/data/canonical_content_v2.json")


@dataclass
class ContentLoadResult:
    records: list[ContentDocument]
    raw_records_by_id: dict[str, ContentRawRecord]
    source: str
    total_rows: int
    duplicate_id_count: int
    missing_key_field_count: int


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _safe_list_str(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        text = _safe_str(item).strip()
        if text:
            result.append(text)
    return result


def _safe_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_json_file(json_path: Path) -> dict[str, object]:
    started_at = time.perf_counter()
    LOGGER.debug(
        "content json read start | path=%s exists=%s",
        json_path,
        json_path.exists(),
    )
    try:
        content = json_path.read_text(encoding="utf-8")
    except OSError as exc:
        LOGGER.exception("Failed to read content JSON file: %s", json_path)
        raise RuntimeError(f"Failed to read content JSON file: {json_path}") from exc

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        LOGGER.exception("Invalid JSON format in content file: %s", json_path)
        raise ValueError(f"Invalid JSON format: {json_path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Top-level JSON must be an object/dict, got: {type(parsed).__name__}"
        )

    normalized: dict[str, object] = {}
    for raw_key, raw_item in parsed.items():
        normalized[str(raw_key)] = raw_item

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    LOGGER.debug(
        "content json read done | path=%s bytes=%s rows=%s elapsed_ms=%.2f",
        json_path,
        len(content),
        len(normalized),
        elapsed_ms,
    )
    return normalized


def _extract_section_map(item: dict[str, object]) -> dict[str, dict[str, object]]:
    content = _safe_dict(item.get("content"))
    sections = content.get("sections")

    if not isinstance(sections, list):
        return {}

    section_map: dict[str, dict[str, object]] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = _safe_str(section.get("key")).strip()
        if not key:
            continue
        if key in section_map:
            LOGGER.warning("Duplicate section key ignored: id=%s key=%s", item.get("id"), key)
            continue
        section_map[key] = section
    return section_map


def _render_tokens_to_text(tokens: list[dict[str, object]]) -> str:
    parts: list[str] = []

    for token in tokens:
        token_type = _safe_str(token.get("type")).strip()

        if token_type == "text":
            value = _safe_str(token.get("text"))
        elif token_type == "math_inline":
            latex = _safe_str(token.get("latex")).strip()
            value = f"${latex}$" if latex else ""
        elif token_type == "math_display":
            latex = _safe_str(token.get("latex")).strip()
            value = f"$$\n{latex}\n$$" if latex else ""
        elif token_type == "line_break":
            value = "\n"
        elif token_type == "ref":
            ref_text = _safe_str(token.get("text")).strip()
            target_id = _safe_str(token.get("target_id")).strip()
            if ref_text and target_id:
                value = f"{ref_text}({target_id})"
            else:
                value = ref_text or target_id
        else:
            # 兜底策略：尽量保留可读文本，避免信息丢失。
            value = _safe_str(token.get("text")) or _safe_str(token.get("latex"))

        if value:
            parts.append(value)

    return _normalize_text("".join(parts))


def _render_sub_blocks_to_text(raw_blocks: object) -> str:
    if not isinstance(raw_blocks, list):
        return ""

    rendered: list[str] = []
    for sub_block in raw_blocks:
        if not isinstance(sub_block, dict):
            continue
        text = _render_block_to_text(sub_block)
        if text:
            rendered.append(text)

    return _normalize_text("\n".join(rendered))


def _render_block_to_text(block: dict[str, object]) -> str:
    block_type = _safe_str(block.get("type")).strip()

    if block_type == "paragraph":
        raw_tokens = block.get("tokens")
        tokens = [x for x in raw_tokens if isinstance(x, dict)] if isinstance(raw_tokens, list) else []
        return _render_tokens_to_text(tokens)

    if block_type == "math_block":
        latex = _safe_str(block.get("latex")).strip()
        return f"$$\n{latex}\n$$" if latex else ""

    if block_type == "divider":
        return "---"

    if block_type == "bullet_list":
        raw_items = block.get("items")
        if not isinstance(raw_items, list):
            return ""

        items: list[str] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            raw_tokens = item.get("tokens")
            tokens = [x for x in raw_tokens if isinstance(x, dict)] if isinstance(raw_tokens, list) else []
            text = _render_tokens_to_text(tokens)
            if text:
                items.append(f"- {text}")

        return _normalize_text("\n".join(items))

    if block_type == "theorem_group":
        raw_items = block.get("items")
        if not isinstance(raw_items, list):
            return ""

        rendered_items: list[str] = []
        for theorem in raw_items:
            if not isinstance(theorem, dict):
                continue

            lines: list[str] = []
            title = _safe_str(theorem.get("title")).strip()
            if title:
                lines.append(title)

            raw_desc_tokens = theorem.get("desc_tokens")
            desc_tokens = (
                [x for x in raw_desc_tokens if isinstance(x, dict)]
                if isinstance(raw_desc_tokens, list)
                else []
            )
            desc_text = _render_tokens_to_text(desc_tokens)
            if desc_text:
                lines.append(desc_text)

            formula_latex = _safe_str(theorem.get("formula_latex")).strip()
            if formula_latex:
                lines.append(f"$$\n{formula_latex}\n$$")

            if lines:
                rendered_items.append(_normalize_text("\n".join(lines)))

        return _normalize_text("\n\n".join(rendered_items))

    if block_type == "proof_steps":
        raw_steps = block.get("steps")
        if not isinstance(raw_steps, list):
            return ""

        rendered_steps: list[str] = []
        for step in raw_steps:
            if not isinstance(step, dict):
                continue

            lines: list[str] = []
            step_title = _safe_str(step.get("title")).strip()
            if step_title:
                lines.append(step_title)

            content_text = _render_sub_blocks_to_text(step.get("content"))
            if content_text:
                lines.append(content_text)

            if lines:
                rendered_steps.append(_normalize_text("\n".join(lines)))

        return _normalize_text("\n\n".join(rendered_steps))

    if block_type in {"warning", "summary_box"}:
        lines: list[str] = []
        title = _safe_str(block.get("title")).strip()
        if title:
            lines.append(title)

        content_text = _render_sub_blocks_to_text(block.get("content"))
        if content_text:
            lines.append(content_text)

        return _normalize_text("\n".join(lines))

    if block_type == "example":
        lines: list[str] = []
        title = _safe_str(block.get("title")).strip()
        if title:
            lines.append(title)

        for label, key in (("题目", "problem"), ("解答", "solution"), ("答案", "answer")):
            section_text = _render_sub_blocks_to_text(block.get(key))
            if section_text:
                lines.append(f"{label}：\n{section_text}")

        return _normalize_text("\n".join(lines))

    # 兜底策略：未知 block 类型时，尽量输出可读文本。
    text = _safe_str(block.get("text")).strip()
    if text:
        return text

    latex = _safe_str(block.get("latex")).strip()
    if latex:
        return f"$$\n{latex}\n$$"

    raw_tokens = block.get("tokens")
    tokens = [x for x in raw_tokens if isinstance(x, dict)] if isinstance(raw_tokens, list) else []
    if tokens:
        return _render_tokens_to_text(tokens)

    return ""


def _render_section_to_text(section: dict[str, object]) -> str:
    raw_blocks = section.get("blocks")
    if not isinstance(raw_blocks, list):
        return ""

    parts: list[str] = []
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue
        text = _render_block_to_text(block)
        if text:
            parts.append(text)

    return _normalize_text("\n\n".join(parts))


def _render_section_to_list(section: dict[str, object]) -> list[str]:
    raw_blocks = section.get("blocks")
    if not isinstance(raw_blocks, list):
        return []

    items: list[str] = []
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue

        block_type = _safe_str(block.get("type")).strip()

        if block_type == "bullet_list":
            raw_list_items = block.get("items")
            if isinstance(raw_list_items, list):
                for list_item in raw_list_items:
                    if not isinstance(list_item, dict):
                        continue
                    raw_tokens = list_item.get("tokens")
                    tokens = (
                        [x for x in raw_tokens if isinstance(x, dict)]
                        if isinstance(raw_tokens, list)
                        else []
                    )
                    text = _render_tokens_to_text(tokens)
                    if text:
                        items.append(text)
            continue

        if block_type == "theorem_group":
            raw_theorem_items = block.get("items")
            if isinstance(raw_theorem_items, list):
                for theorem in raw_theorem_items:
                    if not isinstance(theorem, dict):
                        continue
                    lines: list[str] = []
                    title = _safe_str(theorem.get("title")).strip()
                    if title:
                        lines.append(title)

                    raw_desc_tokens = theorem.get("desc_tokens")
                    desc_tokens = (
                        [x for x in raw_desc_tokens if isinstance(x, dict)]
                        if isinstance(raw_desc_tokens, list)
                        else []
                    )
                    desc_text = _render_tokens_to_text(desc_tokens)
                    if desc_text:
                        lines.append(desc_text)

                    formula_latex = _safe_str(theorem.get("formula_latex")).strip()
                    if formula_latex:
                        lines.append(f"$$\n{formula_latex}\n$$")

                    merged = _normalize_text("\n".join(lines))
                    if merged:
                        items.append(merged)
            continue

        text = _render_block_to_text(block)
        if text:
            items.append(text)

    # 当结构较复杂无法细拆时，允许退化为单条拼接文本。
    if items:
        return items

    fallback = _render_section_to_text(section)
    return [fallback] if fallback else []


def _build_statement_clean(statement: str, primary_formula: str, title: str) -> str:
    candidate = ""
    for value in (statement, primary_formula, title):
        text = _safe_str(value).strip()
        if text:
            candidate = text
            break

    return _normalize_text(candidate)


def _convert_item_to_content_document(raw_key: str, item: dict[str, object]) -> ContentDocument:
    identity = _safe_dict(item.get("identity"))
    meta = _safe_dict(item.get("meta"))
    content = _safe_dict(item.get("content"))
    section_map = _extract_section_map(item)

    conclusion_id = _safe_str(item.get("id")).strip() or _safe_str(raw_key).strip()

    title = _safe_str(meta.get("title"))
    module = _safe_str(identity.get("module"))

    raw_difficulty = meta.get("difficulty", 1)
    try:
        difficulty = int(raw_difficulty if raw_difficulty is not None else 1)
    except (TypeError, ValueError):
        difficulty = 1

    tags = _safe_list_str(meta.get("tags"))

    statement = _render_section_to_text(section_map.get("statement", {}))
    explanation = _render_section_to_text(section_map.get("explanation", {}))
    proof = _render_section_to_text(section_map.get("proof", {}))
    examples = _render_section_to_list(section_map.get("examples", {}))
    traps = _render_section_to_list(section_map.get("traps", {}))

    summary = _safe_str(meta.get("summary"))
    primary_formula = _safe_str(content.get("primary_formula"))
    statement_clean = _build_statement_clean(
        statement=statement,
        primary_formula=primary_formula,
        title=title,
    )

    return {
        "id": conclusion_id,
        "title": title,
        "module": module,
        "difficulty": difficulty,
        "tags": tags,
        "statement_clean": statement_clean,
        "statement": statement,
        "explanation": explanation,
        "proof": proof,
        "examples": examples,
        "traps": traps,
        "summary": summary,
        "pdf_url": None,
    }


def load_content_from_json(json_path: str | Path) -> ContentLoadResult:
    started_at = time.perf_counter()
    path = Path(json_path)
    if not path.is_absolute():
        path = path.resolve()

    raw_items = _load_json_file(path)

    records: list[ContentDocument] = []
    raw_records_by_id: dict[str, ContentRawRecord] = {}
    seen_ids: set[str] = set()
    duplicate_id_count = 0
    missing_key_field_count = 0

    for raw_key, raw_item in raw_items.items():
        item = _safe_dict(raw_item)

        doc = _convert_item_to_content_document(raw_key=raw_key, item=item)
        conclusion_id = _safe_str(doc["id"]).strip()

        if conclusion_id in seen_ids:
            duplicate_id_count += 1
            LOGGER.warning("Duplicate conclusion id detected and skipped: id=%s", conclusion_id)
            continue
        seen_ids.add(conclusion_id)

        raw_record = deepcopy(item)
        if not _safe_str(raw_record.get("id")).strip():
            raw_record["id"] = conclusion_id
        raw_records_by_id[conclusion_id] = raw_record

        if not _safe_str(doc["id"]).strip():
            missing_key_field_count += 1
        if not _safe_str(doc["title"]).strip():
            missing_key_field_count += 1
        if not _safe_str(doc["module"]).strip():
            missing_key_field_count += 1
        if not _safe_str(doc["statement_clean"]).strip():
            missing_key_field_count += 1

        records.append(doc)

    result = ContentLoadResult(
        records=records,
        raw_records_by_id=raw_records_by_id,
        source=f"json:{path.as_posix()}",
        total_rows=len(raw_items),
        duplicate_id_count=duplicate_id_count,
        missing_key_field_count=missing_key_field_count,
    )

    LOGGER.info(
        (
            "Content loaded from JSON: path=%s total_rows=%s records=%s "
            "duplicate_id_count=%s missing_key_field_count=%s"
        ),
        path,
        result.total_rows,
        len(result.records),
        result.duplicate_id_count,
        result.missing_key_field_count,
    )
    LOGGER.debug(
        "content load elapsed | path=%s elapsed_ms=%.2f",
        path,
        (time.perf_counter() - started_at) * 1000,
    )

    return result


def load_content(json_path: str | Path = DEFAULT_CONTENT_JSON_PATH) -> ContentLoadResult:
    """统一入口，供启动链路调用。"""
    return load_content_from_json(json_path)


def load_content_from_sqlite(
    _db: object | None = None,
    json_path: str | Path = DEFAULT_CONTENT_JSON_PATH,
) -> ContentLoadResult:
    """
    历史兼容入口：
    - 函数名来自旧版本（SQLite 内容加载）。
    - 当前底层数据源已切换为 canonical JSON。
    - 不再依赖 SQLite 的 conclusions 表。
    """
    LOGGER.warning(
        "load_content_from_sqlite is a legacy alias; now loading from JSON instead."
    )
    return load_content_from_json(json_path)
