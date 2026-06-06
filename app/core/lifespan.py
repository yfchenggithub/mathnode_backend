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
from app.loaders.pdf_mapping_loader import load_pdf_mapping
from app.stores.memory_content_store import MemoryContentStore
from app.stores.memory_index_store import MemoryIndexStore
from app.stores.memory_pdf_mapping_store import MemoryPdfMappingStore

LOGGER = logging.getLogger(__name__)


def _resolve_project_path(raw_path: str) -> Path:
    """将配置路径规范为绝对路径（支持相对项目根目录）。"""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path

    project_root = Path(__file__).resolve().parents[2]
    return (project_root / path).resolve()


def _resolve_runtime_path(raw_path: str) -> Path:
    """Resolve absolute or project-relative runtime path."""
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return _resolve_project_path(raw_path)


def _check_handout_cjk_font_startup() -> dict[str, str | bool | int | None]:
    """
    Startup self-check for handout CJK font availability.
    This check never raises, to avoid blocking unrelated API capabilities.
    """
    from app.services.favorite_handout_service import COMMON_CJK_FONT_CANDIDATES

    configured_raw = settings.HANDOUT_CJK_FONT_PATH.strip()
    configured_resolved: Path | None = None
    configured_exists = False

    selected_path: Path | None = None
    selected_source = "none"

    if configured_raw:
        configured_resolved = _resolve_runtime_path(configured_raw)
        configured_exists = configured_resolved.is_file()
        if configured_exists:
            selected_path = configured_resolved
            selected_source = "configured"

    if selected_path is None:
        for candidate in COMMON_CJK_FONT_CANDIDATES:
            resolved = _resolve_runtime_path(candidate)
            if resolved.is_file():
                selected_path = resolved
                selected_source = "candidate"
                break

    loadable = False
    load_error: str | None = None

    if selected_path is not None:
        try:
            from PIL import ImageFont

            ImageFont.truetype(str(selected_path), size=12)
            loadable = True
        except Exception as exc:
            load_error = f"{exc.__class__.__name__}: {exc}"
    else:
        load_error = "no_available_font_file"

    result: dict[str, str | bool | int | None] = {
        "handout_font_configured": configured_raw or None,
        "handout_font_configured_resolved": (
            str(configured_resolved) if configured_resolved is not None else None
        ),
        "handout_font_configured_exists": configured_exists,
        "handout_font_selected_source": selected_source,
        "handout_font_selected_path": str(selected_path) if selected_path else None,
        "handout_font_loadable": loadable,
        "handout_font_candidate_count": len(COMMON_CJK_FONT_CANDIDATES),
        "handout_font_load_error": load_error,
    }

    if loadable:
        LOGGER.info(
            (
                "bootstrap handout font check passed | configured=%s resolved=%s "
                "selected_source=%s selected_path=%s"
            ),
            result["handout_font_configured"],
            result["handout_font_configured_resolved"],
            result["handout_font_selected_source"],
            result["handout_font_selected_path"],
        )
    else:
        LOGGER.error(
            (
                "bootstrap handout font check failed | configured=%s resolved=%s "
                "selected_source=%s selected_path=%s error=%s candidates=%s"
            ),
            result["handout_font_configured"],
            result["handout_font_configured_resolved"],
            result["handout_font_selected_source"],
            result["handout_font_selected_path"],
            result["handout_font_load_error"],
            result["handout_font_candidate_count"],
        )

    return result


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    started_at = time.perf_counter()
    LOGGER.info(
        "bootstrap start | env=%s content_backend=%s index_backend=%s biz_backend=%s",
        settings.APP_ENV,
        settings.CONTENT_BACKEND,
        settings.INDEX_BACKEND,
        settings.BIZ_BACKEND,
    )

    try:
        content_json_path = _resolve_project_path(settings.CONTENT_JSON_PATH)
        index_json_path = _resolve_project_path(settings.INDEX_JSON_PATH)
        pdf_mapping_json_path = _resolve_project_path(settings.CONCLUSION_PDF_MAP_PATH)

        LOGGER.info("bootstrap path | sqlite=%s", DATABASE_PATH)
        LOGGER.info("bootstrap path | content_json=%s", content_json_path)
        LOGGER.info("bootstrap path | index_json=%s", index_json_path)
        LOGGER.info("bootstrap path | pdf_mapping_json=%s", pdf_mapping_json_path)

        if settings.BIZ_BACKEND != "sqlite":
            raise RuntimeError(f"Unsupported BIZ_BACKEND: {settings.BIZ_BACKEND}")
        if settings.CONTENT_BACKEND != "memory":
            raise RuntimeError(f"Unsupported CONTENT_BACKEND: {settings.CONTENT_BACKEND}")
        if settings.INDEX_BACKEND != "memory":
            raise RuntimeError(f"Unsupported INDEX_BACKEND: {settings.INDEX_BACKEND}")

        LOGGER.debug("bootstrap step | init_db start")
        init_db()
        LOGGER.debug("bootstrap step | init_db done")

        content_result = load_content(json_path=content_json_path)
        content_store = MemoryContentStore(
            documents=content_result.records,
            source=content_result.source,
            raw_records_by_id=content_result.raw_records_by_id,
        )

        pdf_mapping_result = load_pdf_mapping(
            mapping_json_path=pdf_mapping_json_path,
            pdf_root_dir=settings.PDF_ROOT_DIR,
            strict=settings.PDF_MAPPING_STRICT,
        )
        pdf_mapping_store = MemoryPdfMappingStore(
            mapping=pdf_mapping_result.mapping,
            source=pdf_mapping_result.source,
        )
        index_result = load_index_records(index_file_path=index_json_path)
        index_store = MemoryIndexStore(
            records=index_result.records,
            source=index_result.source,
            generated_at=index_result.generated_at,
            pdf_mapping=pdf_mapping_result.mapping,
            pdf_root_dir=settings.PDF_ROOT_DIR,
        )

        bootstrap_time_ms = int((time.perf_counter() - started_at) * 1000)
        handout_font_check = _check_handout_cjk_font_startup()

        bootstrap_status = {
            "app_env": settings.APP_ENV,
            "sqlite_path": str(DATABASE_PATH),
            "content_json_path": str(content_json_path),
            "index_json_path": str(index_json_path),
            "pdf_mapping_json_path": str(pdf_mapping_json_path),
            "content_backend": settings.CONTENT_BACKEND,
            "index_backend": settings.INDEX_BACKEND,
            "biz_backend": settings.BIZ_BACKEND,
            "pdf_mapping_strict": settings.PDF_MAPPING_STRICT,
            "content_source": content_result.source,
            "index_source": index_result.source,
            "index_generated_at": index_result.generated_at,
            "pdf_mapping_source": pdf_mapping_result.source,
            "content_store": content_store.__class__.__name__,
            "index_store": index_store.__class__.__name__,
            "pdf_mapping_store": pdf_mapping_store.__class__.__name__,
            "content_count": content_store.count(),
            "index_count": index_store.count(),
            "pdf_mapping_count": pdf_mapping_store.count(),
            "duplicate_id_count": content_result.duplicate_id_count,
            "content_missing_key_field_count": content_result.missing_key_field_count,
            "index_missing_key_field_count": index_result.missing_key_field_count,
            "pdf_mapping_total_rows": pdf_mapping_result.total_rows,
            "pdf_mapping_valid_rows": pdf_mapping_result.valid_rows,
            "pdf_mapping_invalid_row_count": pdf_mapping_result.invalid_row_count,
            "pdf_mapping_duplicate_id_count": pdf_mapping_result.duplicate_id_count,
            "bootstrap_time_ms": bootstrap_time_ms,
            "memory_mode_enabled": (
                settings.CONTENT_BACKEND == "memory"
                and settings.INDEX_BACKEND == "memory"
            ),
            **handout_font_check,
        }

        app.state.content_store = content_store
        app.state.index_store = index_store
        app.state.pdf_mapping_store = pdf_mapping_store
        app.state.bootstrap_status = bootstrap_status

        LOGGER.info("bootstrap complete | content_source=%s", bootstrap_status["content_source"])
        LOGGER.info("bootstrap complete | index_source=%s", bootstrap_status["index_source"])
        LOGGER.info("bootstrap complete | content_count=%s", bootstrap_status["content_count"])
        LOGGER.info("bootstrap complete | index_count=%s", bootstrap_status["index_count"])
        LOGGER.info(
            "bootstrap complete | pdf_mapping_count=%s",
            bootstrap_status["pdf_mapping_count"],
        )
        LOGGER.info(
            "bootstrap complete | bootstrap_time_ms=%s",
            bootstrap_status["bootstrap_time_ms"],
        )
        LOGGER.info("bootstrap complete | content_store=%s", bootstrap_status["content_store"])
        LOGGER.info("bootstrap complete | index_store=%s", bootstrap_status["index_store"])
        LOGGER.info(
            "bootstrap complete | pdf_mapping_store=%s",
            bootstrap_status["pdf_mapping_store"],
        )
        LOGGER.info(
            "bootstrap complete | duplicate_id_count=%s",
            bootstrap_status["duplicate_id_count"],
        )
        LOGGER.info(
            "bootstrap complete | content_missing_key_field_count=%s",
            bootstrap_status["content_missing_key_field_count"],
        )
        LOGGER.info(
            "bootstrap complete | index_missing_key_field_count=%s",
            bootstrap_status["index_missing_key_field_count"],
        )
        LOGGER.info(
            "bootstrap complete | pdf_mapping_invalid_row_count=%s",
            bootstrap_status["pdf_mapping_invalid_row_count"],
        )
        LOGGER.info(
            "bootstrap complete | memory_mode_enabled=%s",
            bootstrap_status["memory_mode_enabled"],
        )

        if settings.BOOTSTRAP_LOG_VERBOSE:
            LOGGER.info("bootstrap complete | bootstrap_status=%s", bootstrap_status)
    except Exception:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        LOGGER.exception("bootstrap failed | elapsed_ms=%s", elapsed_ms)
        raise

    try:
        yield
    finally:
        LOGGER.info("shutdown start")
        LOGGER.info("shutdown complete")
