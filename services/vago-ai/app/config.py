"""
全局配置模块。

所有可配置项均通过环境变量或 .env 文件注入，
由 pydantic-settings 自动解析并提供类型校验。

Provider 兼容策略：
  - Embedding 和 LLM 各自维护独立的 api_key / base_url，
    支持同一个服务使用不同 Provider（如 Embedding 走 OpenAI、LLM 走阿里云百炼）。
  - 当 embed_api_key / embed_base_url 为空时，自动回退到 llm_api_key / llm_base_url。
  - base_url 为空时使用各 SDK 的默认 OpenAI 官方端点。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用级配置，字段名即对应的环境变量名（pydantic-settings 自动大写匹配）。"""

    # ── Embedding 模型配置 ──────────────────────────────────────────────────────
    # 支持任何 OpenAI 兼容的 Embedding 端点（OpenAI / 阿里云百炼 / DeepSeek 等）
    openai_api_key: str = ""            # Embedding API Key（历史字段，兼容旧配置）
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = 1536    # 须与 embedding 模型输出维度一致
    embed_api_key: str = ""             # 优先级高于 openai_api_key，空时回退
    embed_base_url: str = ""            # 空 = 使用 OpenAI 官方端点

    # ── LLM (Chat) 模型配置 ────────────────────────────────────────────────────
    # 支持任何 OpenAI Chat Completions 兼容接口
    llm_api_key: str = ""
    llm_base_url: str = ""              # 空 = 使用 OpenAI 官方端点
    llm_model: str = "gpt-4o-mini"     # 可替换为 qwen-plus / deepseek-chat 等
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096   # 旅行规划类长文回答需要更大的输出空间；可通过 LLM_MAX_TOKENS 环境变量覆盖

    # ── Qdrant 向量数据库 ──────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "vago_articles"

    # ── 分块参数 ───────────────────────────────────────────────────────────────
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64

    # ── 内容限制 ───────────────────────────────────────────────────────────────
    max_content_chars: int = 50000

    # ── RAG 检索参数默认值 ─────────────────────────────────────────────────────
    rag_top_k: int = 6
    rag_score_threshold: float = 0.55

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # ── 派生属性（运行时计算，非 env 字段） ────────────────────────────────────

    def get_embed_api_key(self) -> str:
        """
        返回最终生效的 Embedding API Key。

        优先级：embed_api_key > openai_api_key > llm_api_key。
        """
        return self.embed_api_key or self.openai_api_key or self.llm_api_key

    def get_embed_base_url(self) -> str | None:
        """
        返回最终生效的 Embedding base_url。

        空字符串时返回 None，让 OpenAI SDK 使用官方默认端点。
        """
        return self.embed_base_url or None

    def get_llm_api_key(self) -> str:
        """
        返回最终生效的 LLM API Key。

        优先级：llm_api_key > openai_api_key。
        """
        return self.llm_api_key or self.openai_api_key

    def get_llm_base_url(self) -> str | None:
        """
        返回最终生效的 LLM base_url。

        空字符串时返回 None，让 ChatOpenAI 使用 OpenAI 官方端点。
        """
        return self.llm_base_url or None


settings = Settings()
