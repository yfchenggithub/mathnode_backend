from app.core.exceptions import BizException
from app.data.mock_data import MOCK_CONCLUSIONS, MOCK_FAVORITES


class FavoriteService:
    @staticmethod
    def add_favorite(user_id: str, conclusion_id: str) -> None:
        exists = any(item["id"] == conclusion_id for item in MOCK_CONCLUSIONS)
        if not exists:
            raise BizException(code=4040, message="结论不存在")

        if user_id not in MOCK_FAVORITES:
            MOCK_FAVORITES[user_id] = set()

        MOCK_FAVORITES[user_id].add(conclusion_id)

    @staticmethod
    def remove_favorite(user_id: str, conclusion_id: str) -> None:
        if user_id not in MOCK_FAVORITES:
            return
        MOCK_FAVORITES[user_id].discard(conclusion_id)

    @staticmethod
    def list_favorites(user_id: str) -> dict:
        ids = MOCK_FAVORITES.get(user_id, set())
        items = []

        for item in MOCK_CONCLUSIONS:
            if item["id"] in ids:
                items.append(
                    {
                        "conclusion_id": item["id"],
                        "title": item["title"],
                        "module": item["module"],
                    }
                )

        return {
            "total": len(items),
            "items": items,
        }

    @staticmethod
    def get_favorite_ids(user_id: str) -> set[str]:
        return MOCK_FAVORITES.get(user_id, set())
