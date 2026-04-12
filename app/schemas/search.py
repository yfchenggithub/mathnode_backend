from pydantic import BaseModel, ConfigDict, Field


class SearchItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
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


class SuggestItem(BaseModel):
    id: str
    title: str
    subtitle: str
    route: str
    module: str
    difficulty: int
    tags: list[str] = Field(default_factory=list)
    match_type: str
    match_field: str
    matched_text: str
    score: float
    badge: str = ""


class SuggestResponseData(BaseModel):
    query: str = ""
    total: int = 0
    empty_hint: str = ""
    items: list[SuggestItem] = Field(default_factory=list)


class SearchQueryParams(BaseModel):
    q: str = Field(default="")
    module: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    tag: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)
