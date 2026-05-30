from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class FavoriteHandoutStatus(str, Enum):
    ready = "ready"
    processing = "processing"
    failed = "failed"
    expired = "expired"


class FavoriteHandoutErrorInfo(BaseModel):
    code: str
    message: str


class MissingSourcePdfItem(BaseModel):
    conclusion_id: str
    title: str


class FavoriteHandoutResponse(BaseModel):
    handout_id: str
    title: str
    status: FavoriteHandoutStatus
    item_count: int
    filename: str | None
    pdf_url: str | None
    created_at: datetime
    expires_at: datetime | None
    error: FavoriteHandoutErrorInfo | None = None


class FavoriteHandoutCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
