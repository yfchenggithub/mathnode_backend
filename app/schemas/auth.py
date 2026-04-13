from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="login code")


class WechatMiniAppLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="wx.login() code")
    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


class LoginResponseData(BaseModel):
    user_id: str
    nickname: str
    avatar_url: str | None = None
    token: str
    token_type: str = "Bearer"
    expires_in: int
    platform: str
    auth_provider: str
