"""
用途：
- 搜索业务编排层
职责：
- 面向 router 提供 search/suggest
- 依赖抽象 IndexStore，避免请求期直接触达 SQLite
"""

from app.stores.interfaces import IndexStore


class SearchService:
    @staticmethod
    def search(
        index_store: IndexStore,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None = None,
    ) -> dict:
        return index_store.search(
            q=q,
            module=module,
            difficulty=difficulty,
            tag=tag,
            page=page,
            page_size=page_size,
            favorite_ids=favorite_ids,
        )

    @staticmethod
    def suggest(index_store: IndexStore, q: str) -> dict:
        return index_store.suggest(q=q)
