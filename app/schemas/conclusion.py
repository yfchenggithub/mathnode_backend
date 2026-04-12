from pydantic import BaseModel


class ConclusionDetail(BaseModel):
    id: str
    title: str
    module: str
    difficulty: int
    tags: list[str]
    statement: str
    explanation: str
    proof: str
    examples: list[str]
    traps: list[str]
    summary: str
    pdf_url: str | None = None
    pdf_filename: str | None = None
    pdf_available: bool = False
    is_favorited: bool = False
