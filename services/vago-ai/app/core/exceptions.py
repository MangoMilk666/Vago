"""统一异常类型与 FastAPI 异常处理器。"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """可预期业务异常的基类，供后续 auth/trip/knowledge 等模块复用。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "APP_ERROR",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
        },
    )


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """将业务异常渲染为稳定 JSON 响应，方便 Web 与 iOS 统一处理。"""
    return _error_response(exc.status_code, exc.code, exc.message)


async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """将请求参数校验错误转换为统一响应格式。"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "details": exc.errors(),
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """兜底处理未知异常，避免向客户端泄露内部实现细节。"""
    logger.error("Unhandled application error: %s", exc, exc_info=True)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_SERVER_ERROR",
        "服务暂时不可用，请稍后再试",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 应用注册统一异常处理器。"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
