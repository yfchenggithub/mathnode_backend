from pydantic import BaseModel, Field


class RecentSearchCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)


class RecentSearchItem(BaseModel):
    keyword: str
    created_at: str


class RecentSearchListResponseData(BaseModel):
    total: int
    items: list[RecentSearchItem]
