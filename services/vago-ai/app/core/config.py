"""
应用配置模块。

这里是 Phase 1 FastAPI 后端地基的统一配置入口。旧的 ``app.config``
会继续转发这里的 Settings / settings，保证现有 RAG 管道在渐进迁移期间
无需大面积改 import 路径。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """从环境变量或 .env 加载的类型化应用配置。"""

    app_name: str = "Vago API"
    app_version: str = "0.4.0-remould-phase4"
    api_v1_prefix: str = "/api/v1"
    environment: str = "local"
    debug: bool = False

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:8080",
        ]
    )

    # Embedding 模型配置，保留旧字段以兼容现有向量化管道。
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = 1536
    embed_api_key: str = ""
    embed_base_url: str = ""

    # LLM 配置，支持 OpenAI 兼容 Provider。
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Qdrant 向量数据库配置。
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    qdrant_collection: str = "vago_articles"
    # 是否启用可选的语义索引能力；关闭后个人知识 CRUD 与文件读取仍可正常工作。
    rag_enabled: bool = True

    # 攻略文本分块参数。
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64

    # 内容长度限制，避免单篇攻略过大导致索引链路失控。
    max_content_chars: int = 50000

    # 本地开发阶段的个人知识源原文件存储位置与单文件大小上限。
    knowledge_storage_path: str = "data/knowledge"
    knowledge_max_file_bytes: int = 512000

    # RAG 默认检索参数。
    rag_top_k: int = 6
    rag_score_threshold: float = 0.55

    # 迁移期间与旧 Java 后端共享 JWT 校验配置，保证前端直连 Python 的兼容性。
    jwt_secret_key: str = ""
    jwt_token_name: str = "authorization"
    # ttl: 2 hours
    jwt_access_token_ttl_seconds: int = 7200
    # ttl: 720 hours = 30 days
    jwt_refresh_token_ttl_seconds: int = 2592000

    # 短信验证码参数，先对齐 Java 侧 5 分钟验证码 + 60 秒发送间隔。
    sms_code_ttl_seconds: int = 300
    sms_limit_ttl_seconds: int = 60
    account_cancel_grace_seconds: int = 604800

    # GitHub OAuth 配置；Phase 2 先迁移现有 provider，不主动扩大第三方登录范围。
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_token_url: str = "https://github.com/login/oauth/access_token"
    github_oauth_user_url: str = "https://api.github.com/user"
    github_oauth_emails_url: str = "https://api.github.com/user/emails"

    # Redis 配置，用于 JWT 黑名单、限流等短期状态。
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    # 关系型数据库地基。用分开的 MySQL 字段适配不同环境，避免在 .env 里维护整串连接 URL。
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_db: str = "vago"
    mysql_user: str = "root"
    mysql_password: str = "password"
    mysql_charset: str = "utf8mb4"
    database_echo: bool = False
    database_pool_pre_ping: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def get_embed_api_key(self) -> str:
        """返回最终生效的 Embedding API Key。"""
        return self.embed_api_key or self.openai_api_key or self.llm_api_key

    def get_embed_base_url(self) -> str | None:
        """返回最终生效的 Embedding base_url；为空时交给 SDK 使用默认端点。"""
        return self.embed_base_url or None

    def get_llm_api_key(self) -> str:
        """返回最终生效的 LLM API Key。"""
        return self.llm_api_key or self.openai_api_key

    def get_llm_base_url(self) -> str | None:
        """返回最终生效的 LLM base_url；为空时交给 SDK 使用默认端点。"""
        return self.llm_base_url or None

    def build_database_url(self) -> URL:
        """基于分开的 MySQL 配置构造 SQLAlchemy URL。"""
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_db,
            query={"charset": self.mysql_charset},
        )


@lru_cache
def get_settings() -> Settings:
    """返回缓存后的 Settings 实例，避免每次依赖注入都重新解析 .env。"""
    return Settings()


settings = get_settings()
