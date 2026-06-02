from typing import Literal

from pydantic import BaseModel, Field

ConclusionRequestStatus = Literal["pending", "updated", "ignored"]


class ConclusionRequestCreateRequest(BaseModel):
    query: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=100)
    source: str = Field(default="home", max_length=64)
    page: str = Field(default="home", max_length=64)
    entry: str = Field(default="search_hint", max_length=64)
    result_count: int = Field(default=0, ge=0, le=10000)
    has_result: bool = False
    active_tab: str = Field(default="", max_length=64)


class ConclusionRequestUpdateRequest(BaseModel):
    status: ConclusionRequestStatus