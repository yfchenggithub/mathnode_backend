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


def _env_app_env(default: str = "dev") -> str:
    value = _env_str("APP_ENV", default).lower()
    if value in {"dev", "test", "prod"}:
        return value
    return default


def _default_log_format() -> str:
    app_env = _env_app_env()
    return "detailed" if app_env in {"dev", "test"} else "standard"


def _default_log_level() -> str:
    app_env = _env_app_env()
    if app_env == "test":
        return "WARNING"
    return "INFO"


def _default_app_log_level() -> str:
    app_env = _env_app_env()
    return "DEBUG" if app_env == "dev" else "INFO"


def _default_request_log_enabled() -> bool:
    app_env = _env_app_env()
    return app_env != "test"


class Settings(BaseModel):
    APP_NAME: str = "Math Search API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]

    APP_ENV: str = Field(default_factory=_env_app_env)
    LOG_ENABLED: bool = Field(default_factory=lambda: _env_bool("LOG_ENABLED", True))
    LOG_FORMAT: str = Field(
        default_factory=lambda: _env_str("LOG_FORMAT", _default_log_format())
    )
    LOG_LEVEL: str = Field(
        default_factory=lambda: _env_str("LOG_LEVEL", _default_log_level())
    )
    APP_LOG_LEVEL: str = Field(
        default_factory=lambda: _env_str("APP_LOG_LEVEL", _default_app_log_level())
    )
    THIRD_PARTY_LOG_LEVEL: str = Field(
        default_factory=lambda: _env_str("THIRD_PARTY_LOG_LEVEL", "WARNING")
    )
    UVICORN_LOG_LEVEL: str = Field(
        default_factory=lambda: _env_str("UVICORN_LOG_LEVEL", "INFO")
    )
    UVICORN_ACCESS_LOG: bool = Field(
        default_factory=lambda: _env_bool("UVICORN_ACCESS_LOG", False)
    )
    REQUEST_LOG_ENABLED: bool = Field(
        default_factory=lambda: _env_bool(
            "REQUEST_LOG_ENABLED", _default_request_log_enabled()
        )
    )
    REQUEST_LOG_LEVEL: str = Field(
        default_factory=lambda: _env_str("REQUEST_LOG_LEVEL", "INFO")
    )
    HTTP_CLIENT_DEBUG: bool = Field(
        default_factory=lambda: _env_bool("HTTP_CLIENT_DEBUG", False)
    )
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
    JWT_SECRET: str = Field(
        default_factory=lambda: _env_str("JWT_SECRET", "wx283419118cbfff52")
    )
    JWT_EXPIRE_SECONDS: int = Field(
        default_factory=lambda: _env_int("JWT_EXPIRE_SECONDS", 86400)
    )


settings = Settings()
