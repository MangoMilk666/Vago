"""
Embedding 向量化模块（Embedder）。

调用 OpenAI Embeddings API 将文本块转换为高维向量，
供后续写入 Qdrant 向量数据库和相似度检索使用。

模型：text-embedding-3-small（1536 维，性价比最优）
批次策略：每次最多 100 条，防止单批 token 超限（API 上限 300,000 tokens/批）。
"""

from openai import AsyncOpenAI

from app.config import settings

# 模块级单例，避免每次调用重复初始化 HTTP 连接池。
# 注意：base_url 或 api_key 变更时需重启服务使新配置生效。
_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """
    懒加载并返回 AsyncOpenAI Embedding 客户端单例。

    优先使用 settings.embed_api_key / embed_base_url，
    回退顺序为：embed_api_key → openai_api_key → llm_api_key，
    支持 Embedding 与 LLM 使用不同 Provider（如 Embedding 用 OpenAI、LLM 用阿里云百炼）。

    base_url 为 None 时指向 OpenAI 官方端点；
    指向 DashScope 示例：https://dashscope.aliyuncs.com/compatible-mode/v1

    返回:
        配置好 API Key 和 base_url 的 AsyncOpenAI 实例。
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.get_embed_api_key(),
            base_url=settings.get_embed_base_url(),
        )
    return _openai_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    将文本列表批量向量化，返回对应的 embedding 向量列表。

    按 BATCH_SIZE=100 分批调用 OpenAI Embeddings API，
    避免单次请求 token 数过多（text-embedding-3-small 单批上限约 300k tokens）。
    结果列表与输入列表严格一一对应，顺序保证。

    参数:
        texts: 需要向量化的文本列表，通常为分块后的 chunk 列表。

    返回:
        与输入等长的 embedding 向量列表，每个向量维度为 1536（text-embedding-3-small）。
        输入为空列表时，返回空列表。

    异常:
        openai.APIError / openai.RateLimitError 等，由调用方（indexer）处理。
    """
    if not texts:
        return []

    client = _get_client()
    BATCH_SIZE = 100
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
        )
        # response.data 按输入顺序返回，直接 extend
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


async def embed_query(query: str) -> list[float]:
    """
    将单条查询文本向量化，用于 RAG 检索阶段。

    与 embed_texts 相比，专门针对单条文本优化，
    省去批次分割逻辑，调用更直接。

    参数:
        query: 用户输入的自然语言检索问题。

    返回:
        长度为 1536 的 float 向量。

    异常:
        openai.APIError 等，由调用方处理。
    """
    client = _get_client()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=[query],
    )
    return response.data[0].embedding
