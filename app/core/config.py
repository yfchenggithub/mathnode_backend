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


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


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
    PDF_ROOT_DIR: str = Field(
        default_factory=lambda: _env_str("PDF_ROOT_DIR", "app/data/pdfs")
    )
    CONCLUSION_PDF_MAP_PATH: str = Field(
        default_factory=lambda: _env_str(
            "CONCLUSION_PDF_MAP_PATH",
            "app/data/conclusion_pdf_map.json",
        )
    )
    PDF_MAPPING_STRICT: bool = Field(
        default_factory=lambda: _env_bool("PDF_MAPPING_STRICT", False)
    )
    WECHAT_MINIAPP_APPID: str = Field(
        default_factory=lambda: _env_str("WECHAT_MINIAPP_APPID", "wx283419118cbfff52")
    )
    WECHAT_MINIAPP_SECRET: str = Field(
        default_factory=lambda: _env_str(
            "WECHAT_MINIAPP_SECRET", "e69fc3bf3e9b170707711daa03f5cba7"
        )
    )
    JWT_SECRET: str = Field(default_factory=lambda: _env_str("JWT_SECRET", ""))
    JWT_EXPIRE_SECONDS: int = Field(
        default_factory=lambda: _env_int("JWT_EXPIRE_SECONDS", 86400)
    )


settings = Settings()
