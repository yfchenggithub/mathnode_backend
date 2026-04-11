"""
用途：
- 定义 content/index 的存储接口协议
- 让 service 仅依赖抽象，后续可平滑切换后端（JSON、PostgreSQL、搜索引擎）
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict

ContentRawRecord = dict[str, Any]


class ContentDocument(TypedDict):
    id: str
    title: str
    module: str
    difficulty: int
    tags: list[str]
    statement_clean: str
    statement: str
    explanation: str
    proof: str
    examples: list[str]
    traps: list[str]
    summary: str
    pdf_url: str | None


class ContentSummary(TypedDict):
    id: str
    title: str
    module: str


class ContentStore(Protocol):
    def get_by_id(self, conclusion_id: str) -> ContentDocument | None:
        ...

    def get_raw_by_id(self, conclusion_id: str) -> ContentRawRecord | None:
        ...

    def exists(self, conclusion_id: str) -> bool:
        ...

    def get_summary(self, conclusion_id: str) -> ContentSummary | None:
        ...

    def count(self) -> int:
        ...

    def stats(self) -> dict[str, Any]:
        ...


class IndexStore(Protocol):
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
        ...

    def suggest(self, q: str) -> dict[str, Any]:
        ...

    def count(self) -> int:
        ...

    def stats(self) -> dict[str, Any]:
        ...
