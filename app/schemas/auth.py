from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="小程序登录 code")


class LoginResponseData(BaseModel):
    token: str
    user_id: str
    nickname: str
