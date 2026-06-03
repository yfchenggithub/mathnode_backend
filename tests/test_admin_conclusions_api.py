from __future__ import annotations

import unittest
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_index_store
from app.api.deps import get_current_user_id
from app.api.v1.conclusions import router as conclusions_router
from app.core.exception_handlers import register_exception_handlers


class FakeIndexStore:
    def __init__(self) -> None:
        self.last_search: dict[str, Any] | None = None

    def search(
        self,
        q: str,
        module: str | None,
        difficulty: int | None,
        tag: str | None,
        page: int,
        page_size: int,
        favorite_ids: set[str] | None,
    ) -> dict[str, Any]:
        self.last_search = {
            "q": q,
            "module": module,
            "difficulty": difficulty,
            "tag": tag,
            "page": page,
            "page_size": page_size,
            "favorite_ids": favorite_ids,
        }
        items = [
            {
                "id": "C001",
                "title": "椭圆与圆的距离极值转化",
                "module": "conic",
                "category": "圆锥曲线",
                "tags": ["圆锥曲线"],
                "summary": "圆与椭圆的距离极值。",
                "is_favorited": False,
            }
        ]
        return {
            "query": q,
            "total": len(items),
            "page": page,
            "page_size": page_size,
            "items": items,
            "facets": {"module": [], "difficulty": [], "tags": []},
        }

    def count(self) -> int:
        return 1


class AdminConclusionsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index_store = FakeIndexStore()
        app = FastAPI()
        app.include_router(conclusions_router, prefix="/api/v1")
        register_exception_handlers(app)
        app.dependency_overrides[get_index_store] = lambda: self.index_store
        app.dependency_overrides[get_current_user_id] = lambda: "u1001"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_admin_conclusions_lists_by_module(self) -> None:
        response = self.client.get(
            "/api/v1/admin/conclusions",
            params={"module": "conic", "page": 2, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], "C001")
        self.assertEqual(self.index_store.last_search["module"], "conic")
        self.assertEqual(self.index_store.last_search["page"], 2)
        self.assertEqual(self.index_store.last_search["page_size"], 10)
        self.assertEqual(self.index_store.last_search["favorite_ids"], set())

    def test_admin_conclusions_requires_login(self) -> None:
        app = FastAPI()
        app.include_router(conclusions_router, prefix="/api/v1")
        register_exception_handlers(app)
        app.dependency_overrides[get_index_store] = lambda: self.index_store
        client = TestClient(app)
        try:
            response = client.get("/api/v1/admin/conclusions")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["code"], 4011)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
