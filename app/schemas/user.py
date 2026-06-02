from typing import Literal

from pydantic import BaseModel

UserStatus = Literal["active", "disabled"]


class UserStatusUpdateRequest(BaseModel):
    status: UserStatus
