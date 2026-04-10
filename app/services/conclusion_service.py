"""
用途：
- 结论详情业务编排层
职责：
- 请求期从 ContentStore 获取详情
- 维持现有接口字段结构
"""

from app.core.exceptions import BizException
from app.stores.interfaces import ContentStore


class ConclusionService:
    @staticmethod
    def get_by_id(
        content_store: ContentStore,
        conclusion_id: str,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()

        row = content_store.get_by_id(conclusion_id)
        if not row:
            raise BizException(code=4040, message="结论不存在")

        return {
            "id": row["id"],
            "title": row["title"],
            "module": row["module"],
            "difficulty": row["difficulty"],
            "tags": list(row["tags"]),
            "statement": row["statement"],
            "explanation": row["explanation"],
            "proof": row["proof"],
            "examples": list(row["examples"]),
            "traps": list(row["traps"]),
            "summary": row["summary"],
            "pdf_url": row["pdf_url"],
            "is_favorited": row["id"] in favorite_ids,
        }
