from collections import Counter

from sqlalchemy.orm import Session

from app.repositories.conclusion_repo import ConclusionRepository


class SearchService:
    @staticmethod
    def search(
        db: Session,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()

        rows, total = ConclusionRepository.search(
            db=db,
            q=q,
            module=module,
            difficulty=difficulty,
            tag=tag,
            page=page,
            page_size=page_size,
        )

        facet_rows = ConclusionRepository.list_all_for_facets(
            db=db,
            q=q,
            module=module,
            difficulty=difficulty,
            tag=tag,
        )

        items = []
        for row in rows:
            tags = [x.strip() for x in row.tags.split(",") if x.strip()]
            items.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "module": row.module,
                    "difficulty": row.difficulty,
                    "tags": tags,
                    "statement_clean": row.statement_clean,
                    "is_favorited": row.id in favorite_ids,
                }
            )

        module_counter = Counter(x.module for x in facet_rows)
        difficulty_counter = Counter(x.difficulty for x in facet_rows)
        tags_counter = Counter(
            tag_name.strip()
            for x in facet_rows
            for tag_name in x.tags.split(",")
            if tag_name.strip()
        )

        return {
            "query": q,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "facets": {
                "module": [{"value": k, "count": v} for k, v in module_counter.items()],
                "difficulty": [
                    {"value": k, "count": v} for k, v in difficulty_counter.items()
                ],
                "tags": [{"value": k, "count": v} for k, v in tags_counter.items()],
            },
        }

    @staticmethod
    def suggest(db: Session, q: str) -> dict:
        keyword = q.strip()
        if not keyword:
            return {"items": []}

        rows, _ = ConclusionRepository.search(
            db=db,
            q=keyword,
            module=None,
            difficulty=None,
            tag=None,
            page=1,
            page_size=8,
        )

        return {"items": [row.title for row in rows[:8]]}
