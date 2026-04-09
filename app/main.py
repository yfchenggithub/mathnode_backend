"""
用途：
- FastAPI 应用主入口
- 注册全局异常处理
- 挂载总路由

设计：
- main.py 只做应用装配，不写业务逻辑
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="高中数学二级结论搜索系统后端 API（最小可运行骨架）",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_PREFIX)

    return app


app = create_app()
