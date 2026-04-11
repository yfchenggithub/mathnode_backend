"""
用途：
- 统一项目配置入口。
- 兼容当前纯代码配置，同时支持通过环境变量覆盖关键开关与路径。
职责：
- 对外提供 Settings 单例，供 FastAPI 启动链路与服务层共享配置。
设计说明：
- 保持“环境变量优先，代码默认值兜底”的统一策略，避免路径和开关散落到各模块。
"""

import os

from pydantic import BaseModel, Field


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    APP_NAME: str = "Math Search API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]

    APP_ENV: str = Field(default_factory=lambda: _env_str("APP_ENV", "dev"))
    CONTENT_BACKEND: str = Field(
        default_factory=lambda: _env_str("CONTENT_BACKEND", "memory")
    )
    CONTENT_JSON_PATH: str = Field(
        default_factory=lambda: _env_str(
            "CONTENT_JSON_PATH",
            "app/data/canonical_content_v2.json",
        )
    )
    INDEX_BACKEND: str = Field(
        default_factory=lambda: _env_str("INDEX_BACKEND", "memory")
    )
    INDEX_JSON_PATH: str = Field(
        default_factory=lambda: _env_str(
            "INDEX_JSON_PATH",
            "app/data/backend_search_index.json",
        )
    )
    BIZ_BACKEND: str = Field(default_factory=lambda: _env_str("BIZ_BACKEND", "sqlite"))
    ENABLE_DEBUG_ENDPOINTS: bool = Field(
        default_factory=lambda: _env_bool("ENABLE_DEBUG_ENDPOINTS", False)
    )
    BOOTSTRAP_LOG_VERBOSE: bool = Field(
        default_factory=lambda: _env_bool("BOOTSTRAP_LOG_VERBOSE", True)
    )
    # PDF 文件根目录：可由环境变量覆盖，默认使用项目内目录。
    PDF_ROOT_DIR: str = Field(
        default_factory=lambda: _env_str("PDF_ROOT_DIR", "app/data/pdfs")
    )


settings = Settings()
