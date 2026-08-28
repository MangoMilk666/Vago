"""兼容旧启动命令的 ASGI 入口。

启动命令：
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from app.main import app

__all__ = ["app"]
