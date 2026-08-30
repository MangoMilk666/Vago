"""统一 API 响应 envelope。

新迁移的 auth/users 接口先对齐 Java 侧 ``{code,message,data}`` 形态，
后续前端切流时可以少改调用层。
"""
# Generic: 泛型的抽象基类
# TypeVar: object类的子类，用于【构建接收泛型参数的类】定义
from typing import Generic, TypeVar

from pydantic import BaseModel
# 定义一个泛型类型变量T
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """成功响应 envelope；错误响应由 AppException handler 统一生成。"""

    code: int = 200
    message: str = "success"
    data: T | None = None


def success(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    """构造成功响应，保持与旧 Java Result.success 风格兼容。"""
    return ApiResponse[T](code=200, message=message, data=data)
