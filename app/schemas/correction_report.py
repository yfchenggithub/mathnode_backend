from typing import Literal

from pydantic import BaseModel, Field

CorrectionReportStatus = Literal["pending", "fixed", "ignored"]


class CorrectionReportCreateRequest(BaseModel):
    conclusion_id: str = Field(default="", max_length=32)
    conclusion_title: str = Field(default="", max_length=160)
    error_location: str = Field(default="body", max_length=32)
    error_type: str = Field(default="text", max_length=32)
    description: str = Field(default="", max_length=200)


class CorrectionReportUpdateRequest(BaseModel):
    status: CorrectionReportStatus
