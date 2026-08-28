"""目标 FastAPI 后端的安全与当前用户依赖。"""

from dataclasses import dataclass

from fastapi import Depends

from app.dependencies.auth import get_current_user_uuid


@dataclass(frozen=True)
class CurrentUser:
    """传入 domain service 的已认证用户身份。"""

    user_uuid: str


async def get_current_user(
    user_uuid: str = Depends(get_current_user_uuid),
) -> CurrentUser:
    """把旧 JWT 依赖返回的 user_uuid 包装成类型化当前用户对象。"""
    return CurrentUser(user_uuid=user_uuid)
