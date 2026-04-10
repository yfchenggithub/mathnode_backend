from __future__ import annotations

from app.schemas.content_v2 import ConclusionRecordV2

sample = {
    "id": "I001",
    "schema_version": 2,
    "type": "conclusion",
    "status": "published",
    "identity": {
        "slug": "inequality-equivalent-forms-of-N-fx-M",
        "module": "inequality",
        "knowledge_node": "不等式-等价变形-绝对值转化",
        "alt_nodes": ["不等式-等价变形-分式不等式转化", "函数-综合-函数与不等式"],
    },
    "meta": {
        "title": "连不等式 N < f(x) < M 的四种等价形式",
        "aliases": ["连不等式转化", "不等式等价变形"],
        "difficulty": 2,
        "category": "不等式",
        "tags": ["不等式", "等价转化", "绝对值不等式"],
        "summary": "一个函数值介于两个数之间的不等式，可以等价写成多种形式。",
        "is_pro": False,
        "remarks": "",
    },
    "content": {
        "render_schema_version": 2,
        "primary_formula": "N < f(x) < M",
        "variables": [
            {
                "name": "M",
                "latex": "M",
                "description": "区间上界，实数",
                "required": True,
            },
            {
                "name": "N",
                "latex": "N",
                "description": "区间下界，实数",
                "required": True,
            },
        ],
        "conditions": [
            {
                "id": "c1",
                "title": "基础条件",
                "content": [
                    {"type": "math_inline", "latex": "M, N \\in \\mathbb{R}"},
                    {"type": "text", "text": "，且 "},
                    {"type": "math_inline", "latex": "M > N"},
                ],
                "required": True,
            }
        ],
        "conclusions": [
            {
                "id": "k1",
                "title": "原始形式",
                "content": [{"type": "math_inline", "latex": "N < f(x) < M"}],
            }
        ],
        "sections": [
            {
                "key": "core_formula",
                "title": "核心公式",
                "block_type": "math_block",
                "blocks": [
                    {
                        "id": "b1",
                        "type": "math_block",
                        "latex": "N < f(x) < M",
                        "align": "center",
                    }
                ],
            },
            {
                "key": "explanation",
                "title": "理解与直觉",
                "block_type": "rich_text",
                "blocks": [
                    {
                        "id": "b2",
                        "type": "paragraph",
                        "tokens": [
                            {"type": "text", "text": "连不等式 "},
                            {"type": "math_inline", "latex": "N < f(x) < M"},
                            {"type": "text", "text": " 可通过多种代数形式等价表达。"},
                        ],
                    },
                    {
                        "id": "b3",
                        "type": "warning",
                        "level": "warning",
                        "title": "条件提醒",
                        "content": [
                            {
                                "type": "paragraph",
                                "tokens": [
                                    {"type": "text", "text": "倒数形式需保证 "},
                                    {"type": "math_inline", "latex": "f(x)-N > 0"},
                                ],
                            }
                        ],
                    },
                ],
            },
        ],
        "plain": {
            "statement": "条件：M,N 为实数且 M>N。",
            "explanation": "连不等式可以转成多种形式。",
            "proof": "略。",
            "examples": "略。",
            "traps": "注意倒数形式条件。",
            "summary": "本质是函数值落在开区间内。",
        },
    },
    "assets": {"svg": "I001.svg", "png": "", "pdf": "", "mp4": "", "extra": []},
    "ext": {
        "share": {"title": "连不等式等价转化", "desc": "适合参数范围题速查。"},
        "relations": {
            "prerequisites": ["不等式基本性质", "绝对值不等式解法"],
            "related_ids": [],
            "similar": "分式不等式转化",
        },
        "exam": {"frequency": 0.6, "score": 5},
        "extra": {},
    },
}

record = ConclusionRecordV2.model_validate(sample)

print(record.model_dump())
print(record.model_dump_json(indent=2))
