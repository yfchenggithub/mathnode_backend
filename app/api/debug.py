"""
用途：
- 提供启动态与内存 store 的调试可见性
职责：
- 输出当前 bootstrap 关键指标，便于本地排查
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.response import success_response

router = APIRouter()


@router.get("/debug/store-status")
def get_store_status(request: Request):
    status = getattr(request.app.state, "bootstrap_status", {})

    data = {
        "app_env": status.get("app_env"),
        "content_store": status.get("content_store"),
        "index_store": status.get("index_store"),
        "content_count": status.get("content_count", 0),
        "index_count": status.get("index_count", 0),
        "content_source": status.get("content_source"),
        "index_source": status.get("index_source"),
        "bootstrap_time_ms": status.get("bootstrap_time_ms"),
        "duplicate_id_count": status.get("duplicate_id_count", 0),
        "content_missing_key_field_count": status.get(
            "content_missing_key_field_count", 0
        ),
        "index_missing_key_field_count": status.get(
            "index_missing_key_field_count",
            0,
        ),
        "memory_mode_enabled": status.get("memory_mode_enabled", False),
    }
    return success_response(data=data)
