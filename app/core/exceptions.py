"""
用途：
- 统一异常类与异常处理
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.response import error_response


class BizException(Exception):
    def __init__(self, code: int = 4000, message: str = "业务异常") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        return JSONResponse(
            status_code=400,
            content=error_response(code=exc.code, message=exc.message),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=error_response(code=5000, message="服务器内部错误"),
        )
