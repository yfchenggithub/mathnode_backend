from app.core.exceptions import BizException
from app.data.mock_data import MOCK_CONCLUSIONS


class ConclusionService:
    @staticmethod
    def get_by_id(conclusion_id: str, favorite_ids: set[str] | None = None) -> dict:
        favorite_ids = favorite_ids or set()

        for item in MOCK_CONCLUSIONS:
            if item["id"] == conclusion_id:
                return {
                    "id": item["id"],
                    "title": item["title"],
                    "module": item["module"],
                    "difficulty": item["difficulty"],
                    "tags": item["tags"],
                    "statement": item["statement"],
                    "explanation": item["explanation"],
                    "proof": item["proof"],
                    "examples": item["examples"],
                    "traps": item["traps"],
                    "summary": item["summary"],
                    "pdf_url": item["pdf_url"],
                    "is_favorited": item["id"] in favorite_ids,
                }

        raise BizException(code=4040, message="结论不存在")
