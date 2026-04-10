"""
用途：
- 统一提供 app.state 中 store 的依赖注入
职责：
- 避免在 router 中分散读取 request.app.state
"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.core.exceptions import BizException
from app.stores.interfaces import ContentStore, IndexStore


def get_content_store(request: Request) -> ContentStore:
    store = getattr(request.app.state, "content_store", None)
    if store is None:
        raise BizException(code=5001, message="content store not initialized")
    return cast(ContentStore, store)


def get_index_store(request: Request) -> IndexStore:
    store = getattr(request.app.state, "index_store", None)
    if store is None:
        raise BizException(code=5002, message="index store not initialized")
    return cast(IndexStore, store)
