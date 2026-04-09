from collections import Counter

from app.data.mock_data import MOCK_CONCLUSIONS


class SearchService:
    @staticmethod
    def search(
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        favorite_ids = favorite_ids or set()

        results = []
        keyword = q.strip().lower()

        for item in MOCK_CONCLUSIONS:
            if module and item["module"] != module:
                continue
            if difficulty and item["difficulty"] != difficulty:
                continue
            if tag and tag not in item["tags"]:
                continue

            haystack = " ".join(
                [
                    item["title"],
                    item["module"],
                    item["statement_clean"],
                    " ".join(item["tags"]),
                ]
            ).lower()

            if keyword and keyword not in haystack:
                continue

            result = {
                "id": item["id"],
                "title": item["title"],
                "module": item["module"],
                "difficulty": item["difficulty"],
                "tags": item["tags"],
                "statement_clean": item["statement_clean"],
                "is_favorited": item["id"] in favorite_ids,
            }
            results.append(result)

        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = results[start:end]

        module_counter = Counter(x["module"] for x in results)
        difficulty_counter = Counter(x["difficulty"] for x in results)
        tags_counter = Counter(tag for x in results for tag in x["tags"])

        return {
            "query": q,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": paged_items,
            "facets": {
                "module": [{"value": k, "count": v} for k, v in module_counter.items()],
                "difficulty": [
                    {"value": k, "count": v} for k, v in difficulty_counter.items()
                ],
                "tags": [{"value": k, "count": v} for k, v in tags_counter.items()],
            },
        }

    @staticmethod
    def suggest(q: str) -> dict:
        query = q.strip().lower()
        if not query:
            return {"items": []}

        candidates = []
        for item in MOCK_CONCLUSIONS:
            if (
                query in item["title"].lower()
                or query in item["statement_clean"].lower()
            ):
                candidates.append(item["title"])

        return {"items": list(dict.fromkeys(candidates))[:8]}
