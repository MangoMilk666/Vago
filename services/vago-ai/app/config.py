"""兼容旧代码的配置导入入口。

新模块应直接从 ``app.core.config`` 导入。现有 RAG 代码可以继续使用
``app.config``，这样 remould 迁移不需要一次性修改所有 import。
"""

from app.core.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
