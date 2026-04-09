"""
用途：
- 统一 API 返回结构
"""

from typing import Any


def success_response(data: Any = None, message: str = "ok") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error_response(code: int, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None,
    }
