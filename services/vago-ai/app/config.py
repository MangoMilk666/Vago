"""
全局配置模块。

所有可配置项均通过环境变量或 .env 文件注入，
由 pydantic-settings 自动解析并提供类型校验。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用级配置，字段名即对应的环境变量名（自动大写匹配）。"""

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = 1536

    # Qdrant 向量数据库
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "vago_articles"

    # 分块参数
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64

    # 内容限制
    max_content_chars: int = 50000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
