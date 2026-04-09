from app.core.exceptions import BizException
from app.data.mock_data import MOCK_USERS


class AuthService:
    @staticmethod
    def login(code: str) -> dict:
        user = MOCK_USERS.get(code)
        if not user:
            raise BizException(code=4010, message="登录失败，code 无效")
        return user
