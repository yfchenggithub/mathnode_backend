from pydantic import BaseModel, Field


class WeeklyUpdateAuthorizationRequest(BaseModel):
    template_id: str | None = Field(default=None, max_length=128)
    result: str = Field(..., pattern="^(accept|reject|ban|filter)$")
    source: str | None = Field(default=None, max_length=64)


class WeeklyUpdateNotificationSendRequest(BaseModel):
    project_name: str = Field(default="每周二级结论更新", min_length=1, max_length=20)
    project_progress: str = Field(default="本周新增结论已更新", min_length=1, max_length=20)
    updated_at: str | None = Field(default=None, max_length=32)
    page: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=200, ge=1, le=2000)
