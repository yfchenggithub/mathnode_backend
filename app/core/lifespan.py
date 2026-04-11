"""
用途：
- 应用启动/关闭生命周期管理。
职责：
- 初始化业务数据库（收藏、最近搜索等）。
- 启动期加载 canonical JSON 内容并加载离线检索索引。
- 将 store 与 bootstrap 状态挂载到 app.state。
设计说明：
- 以最小改造接入 FastAPI lifespan，替代 on_event("startup")。
- content loader 与 index loader 解耦，便于索引源后续切换到其他后端。
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import DATABASE_PATH
from app.loaders.content_loader import load_content
from app.loaders.index_loader import load_index_records
from app.stores.memory_content_store import MemoryContentStore
from app.stores.memory_index_store import MemoryIndexStore

LOGGER = logging.getLogger(__name__)


def _resolve_project_path(raw_path: str) -> Path:
    """将配置路径规范为绝对路径（支持相对项目根目录）。"""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path

    project_root = Path(__file__).resolve().parents[2]
    return (project_root / path).resolve()


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    started_at = time.perf_counter()

    content_json_path = _resolve_project_path(settings.CONTENT_JSON_PATH)
    index_json_path = _resolve_project_path(settings.INDEX_JSON_PATH)

    LOGGER.info("Bootstrap start")
    LOGGER.info("SQLite path: %s", DATABASE_PATH)
    LOGGER.info("Content JSON path: %s", content_json_path)
    LOGGER.info("Index JSON path: %s", index_json_path)
    LOGGER.info(
        "Configured backends: content=%s index=%s biz=%s",
        settings.CONTENT_BACKEND,
        settings.INDEX_BACKEND,
        settings.BIZ_BACKEND,
    )

    if settings.BIZ_BACKEND != "sqlite":
        raise RuntimeError(f"Unsupported BIZ_BACKEND: {settings.BIZ_BACKEND}")
    if settings.CONTENT_BACKEND != "memory":
        raise RuntimeError(f"Unsupported CONTENT_BACKEND: {settings.CONTENT_BACKEND}")
    if settings.INDEX_BACKEND != "memory":
        raise RuntimeError(f"Unsupported INDEX_BACKEND: {settings.INDEX_BACKEND}")

    init_db()
    content_result = load_content(json_path=content_json_path)

    content_store = MemoryContentStore(
        documents=content_result.records,
        source=content_result.source,
    )

    index_result = load_index_records(index_file_path=index_json_path)
    index_store = MemoryIndexStore(
        records=index_result.records,
        source=index_result.source,
    )

    bootstrap_time_ms = int((time.perf_counter() - started_at) * 1000)

    bootstrap_status = {
        "app_env": settings.APP_ENV,
        "sqlite_path": str(DATABASE_PATH),
        "content_json_path": str(content_json_path),
        "index_json_path": str(index_json_path),
        "content_backend": settings.CONTENT_BACKEND,
        "index_backend": settings.INDEX_BACKEND,
        "biz_backend": settings.BIZ_BACKEND,
        "content_source": content_result.source,
        "index_source": index_result.source,
        "content_store": content_store.__class__.__name__,
        "index_store": index_store.__class__.__name__,
        "content_count": content_store.count(),
        "index_count": index_store.count(),
        "duplicate_id_count": content_result.duplicate_id_count,
        "content_missing_key_field_count": content_result.missing_key_field_count,
        "index_missing_key_field_count": index_result.missing_key_field_count,
        "bootstrap_time_ms": bootstrap_time_ms,
        "memory_mode_enabled": (
            settings.CONTENT_BACKEND == "memory"
            and settings.INDEX_BACKEND == "memory"
        ),
    }

    app.state.content_store = content_store
    app.state.index_store = index_store
    app.state.bootstrap_status = bootstrap_status

    LOGGER.info("content_source=%s", bootstrap_status["content_source"])
    LOGGER.info("index_source=%s", bootstrap_status["index_source"])
    LOGGER.info("content_count=%s", bootstrap_status["content_count"])
    LOGGER.info("index_count=%s", bootstrap_status["index_count"])
    LOGGER.info("bootstrap_time_ms=%s", bootstrap_status["bootstrap_time_ms"])
    LOGGER.info("content_store=%s", bootstrap_status["content_store"])
    LOGGER.info("index_store=%s", bootstrap_status["index_store"])
    LOGGER.info("duplicate_id_count=%s", bootstrap_status["duplicate_id_count"])
    LOGGER.info(
        "content_missing_key_field_count=%s",
        bootstrap_status["content_missing_key_field_count"],
    )
    LOGGER.info(
        "index_missing_key_field_count=%s",
        bootstrap_status["index_missing_key_field_count"],
    )
    LOGGER.info("memory_mode_enabled=%s", bootstrap_status["memory_mode_enabled"])

    if settings.BOOTSTRAP_LOG_VERBOSE:
        LOGGER.info("bootstrap_status=%s", bootstrap_status)

    try:
        yield
    finally:
        LOGGER.info("Shutdown complete")
