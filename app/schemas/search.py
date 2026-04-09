from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    id: str
    title: str
    module: str
    difficulty: int
    tags: list[str]
    statement_clean: str
    is_favorited: bool = False


class FacetItem(BaseModel):
    value: str | int
    count: int


class SearchFacets(BaseModel):
    module: list[FacetItem] = []
    difficulty: list[FacetItem] = []
    tags: list[FacetItem] = []


class SearchResponseData(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    items: list[SearchItem]
    facets: SearchFacets


class SuggestResponseData(BaseModel):
    items: list[str] = []


class SearchQueryParams(BaseModel):
    q: str = Field(default="")
    module: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    tag: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)
