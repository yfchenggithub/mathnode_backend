import json

from sqlalchemy.orm import Session

from app.core.exceptions import BizException
from app.repositories.conclusion_repo import ConclusionRepository


class ConclusionService:
    @staticmethod
    def get_by_id(
        db: Session,
        conclusion_id: str,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()

        row = ConclusionRepository.get_by_id(db, conclusion_id)
        if not row:
            raise BizException(code=4040, message="结论不存在")

        return {
            "id": row.id,
            "title": row.title,
            "module": row.module,
            "difficulty": row.difficulty,
            "tags": [x.strip() for x in row.tags.split(",") if x.strip()],
            "statement": row.statement,
            "explanation": row.explanation,
            "proof": row.proof,
            "examples": json.loads(row.examples_json or "[]"),
            "traps": json.loads(row.traps_json or "[]"),
            "summary": row.summary,
            "pdf_url": row.pdf_url,
            "is_favorited": row.id in favorite_ids,
        }
