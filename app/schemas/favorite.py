from pydantic import BaseModel, Field


class FavoriteCreateRequest(BaseModel):
    conclusion_id: str = Field(..., min_length=1)


class FavoriteItem(BaseModel):
    conclusion_id: str
    title: str
    module: str


class FavoriteListResponseData(BaseModel):
    total: int
    items: list[FavoriteItem]
