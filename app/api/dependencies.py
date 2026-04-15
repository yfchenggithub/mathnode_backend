"""
用途：
- 统一提供 app.state 中 store 的依赖注入
职责：
- 避免在 router 中分散读取 request.app.state
"""

from __future__ import annotations

import logging
from typing import cast

from fastapi import Request

from app.core.exceptions import BizException
from app.core.request_context import get_request_id
from app.stores.interfaces import ContentStore, IndexStore, PdfMappingStore

LOGGER = logging.getLogger(__name__)


def get_content_store(request: Request) -> ContentStore:
    store = getattr(request.app.state, "content_store", None)
    if store is None:
        LOGGER.error("content store missing | request_id=%s", get_request_id())
        raise BizException(code=5001, message="content store not initialized")
    LOGGER.debug("content store resolved | request_id=%s", get_request_id())
    return cast(ContentStore, store)


def get_index_store(request: Request) -> IndexStore:
    store = getattr(request.app.state, "index_store", None)
    if store is None:
        LOGGER.error("index store missing | request_id=%s", get_request_id())
        raise BizException(code=5002, message="index store not initialized")
    LOGGER.debug("index store resolved | request_id=%s", get_request_id())
    return cast(IndexStore, store)


def get_pdf_mapping_store(request: Request) -> PdfMappingStore:
    store = getattr(request.app.state, "pdf_mapping_store", None)
    if store is None:
        LOGGER.error("pdf mapping store missing | request_id=%s", get_request_id())
        raise BizException(code=5003, message="pdf mapping store not initialized")
    LOGGER.debug("pdf mapping store resolved | request_id=%s", get_request_id())
    return cast(PdfMappingStore, store)
