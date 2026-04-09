"""
用途：
- 项目基础配置
- 后续可切换为 .env + pydantic-settings
"""

from pydantic import BaseModel


class Settings(BaseModel):
    APP_NAME: str = "Math Search API"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
