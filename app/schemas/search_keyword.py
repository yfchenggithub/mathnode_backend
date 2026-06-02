from pydantic import BaseModel


class SearchKeywordItem(BaseModel):
    id: int
    keyword: str
    normalized_keyword: str
    search_count: int
    last_result_count: int
    last_has_result: bool
    created_at: str
    updated_at: str


class SearchKeywordListResponseData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchKeywordItem]
