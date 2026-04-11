"""
用途：
- 校验 content_loader 从 canonical JSON 加载时的核心行为。
覆盖点：
- 成功加载与字段映射。
- section 缺失兜底。
- duplicate_id_count 与 missing_key_field_count 统计。
"""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path

from app.loaders.content_loader import load_content_from_json


class ContentLoaderJsonTests(unittest.TestCase):
    def _write_json(self, payload: dict) -> Path:
        temp_root = Path("tests") / ".tmp"
        temp_root.mkdir(parents=True, exist_ok=True)

        json_path = temp_root / f"content_{uuid.uuid4().hex}.json"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return json_path

    def test_load_json_success_and_mapping(self) -> None:
        payload = {
            "I001": {
                "id": "I001",
                "identity": {"module": "inequality"},
                "meta": {
                    "title": "连不等式",
                    "difficulty": 2,
                    "tags": ["不等式", "等价变形"],
                    "summary": "核心结论摘要",
                },
                "content": {
                    "primary_formula": "N < f(x) < M",
                    "sections": [
                        {
                            "key": "statement",
                            "blocks": [
                                {
                                    "type": "theorem_group",
                                    "items": [
                                        {
                                            "title": "结论一",
                                            "desc_tokens": [
                                                {"type": "text", "text": "函数值在区间内"}
                                            ],
                                            "formula_latex": "N < f(x) < M",
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "key": "explanation",
                            "blocks": [
                                {
                                    "type": "paragraph",
                                    "tokens": [
                                        {"type": "text", "text": "解释："},
                                        {"type": "math_inline", "latex": "N < f(x) < M"},
                                    ],
                                }
                            ],
                        },
                        {
                            "key": "proof",
                            "blocks": [
                                {
                                    "type": "math_block",
                                    "latex": "N < f(x) < M",
                                    "align": "center",
                                }
                            ],
                        },
                        {
                            "key": "examples",
                            "blocks": [
                                {
                                    "type": "paragraph",
                                    "tokens": [{"type": "text", "text": "例1"}],
                                },
                                {
                                    "type": "paragraph",
                                    "tokens": [{"type": "text", "text": "例2"}],
                                },
                            ],
                        },
                        {
                            "key": "traps",
                            "blocks": [
                                {
                                    "type": "bullet_list",
                                    "items": [
                                        {"tokens": [{"type": "text", "text": "易错1"}]},
                                        {"tokens": [{"type": "text", "text": "易错2"}]},
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        }

        result = load_content_from_json(self._write_json(payload))

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.duplicate_id_count, 0)
        self.assertEqual(result.missing_key_field_count, 0)
        self.assertEqual(len(result.records), 1)
        self.assertTrue(result.source.startswith("json:"))

        doc = result.records[0]
        self.assertEqual(doc["id"], "I001")
        self.assertEqual(doc["title"], "连不等式")
        self.assertEqual(doc["module"], "inequality")
        self.assertEqual(doc["difficulty"], 2)
        self.assertEqual(doc["tags"], ["不等式", "等价变形"])
        self.assertEqual(doc["summary"], "核心结论摘要")
        self.assertIsNone(doc["pdf_url"])

        self.assertIn("结论一", doc["statement"])
        self.assertIn("N < f(x) < M", doc["statement"])
        self.assertIn("$N < f(x) < M$", doc["explanation"])
        self.assertIn("$$", doc["proof"])
        self.assertEqual(doc["examples"], ["例1", "例2"])
        self.assertEqual(doc["traps"], ["易错1", "易错2"])
        self.assertTrue(doc["statement_clean"])

    def test_missing_sections_fallback(self) -> None:
        payload = {
            "RAW_KEY_001": {
                "identity": {},
                "meta": {"title": "标题兜底"},
                "content": {
                    "primary_formula": "a+b>0",
                    "sections": [],
                },
            }
        }

        result = load_content_from_json(self._write_json(payload))

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.duplicate_id_count, 0)
        self.assertEqual(result.missing_key_field_count, 1)
        self.assertEqual(len(result.records), 1)

        doc = result.records[0]
        self.assertEqual(doc["id"], "RAW_KEY_001")
        self.assertEqual(doc["module"], "")
        self.assertEqual(doc["difficulty"], 1)
        self.assertEqual(doc["tags"], [])
        self.assertEqual(doc["statement"], "")
        self.assertEqual(doc["explanation"], "")
        self.assertEqual(doc["proof"], "")
        self.assertEqual(doc["examples"], [])
        self.assertEqual(doc["traps"], [])
        self.assertEqual(doc["statement_clean"], "a+b>0")

    def test_duplicate_and_missing_stats(self) -> None:
        payload = {
            "A": {
                "id": "DUP001",
                "identity": {"module": ""},
                "meta": {"title": "", "summary": ""},
                "content": {"sections": []},
            },
            "B": {
                "id": "DUP001",
                "identity": {"module": "algebra"},
                "meta": {"title": "标题"},
                "content": {"sections": []},
            },
        }

        result = load_content_from_json(self._write_json(payload))

        self.assertEqual(result.total_rows, 2)
        self.assertEqual(result.duplicate_id_count, 1)
        self.assertEqual(result.missing_key_field_count, 3)
        self.assertEqual(len(result.records), 1)


if __name__ == "__main__":
    unittest.main()
