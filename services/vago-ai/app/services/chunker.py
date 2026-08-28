"""
语义分块模块（Semantic Chunker）。

将清洗后的长文本按语义边界切分为适合 Embedding 的文本块（chunk）。

分块策略：
  - 优先在段落（\\n\\n）、句末（。！？）、逗号（，；）处断开，避免语义截断；
  - 使用 tiktoken cl100k_base 编码器计算 token 数，保证分块大小对 OpenAI Embedding 模型友好；
  - 默认 chunk_size=512 tokens，overlap=64 tokens。
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken

# cl100k_base 是 text-embedding-3-small / GPT-4 系列使用的 BPE 编码器。
# 懒加载可以避免健康检查、OpenAPI 或非 RAG 测试在 import 阶段触发 tiktoken 网络下载。
_ENCODER = None

# 中文语义分隔符优先级列表（由粗到细）
_CHINESE_SEPARATORS = [
    "\n\n",   # 段落
    "\n",     # 换行
    "。",     # 句号
    "！",     # 感叹号
    "？",     # 问号
    "；",     # 分号
    "，",     # 逗号
    " ",      # 空格
    "",       # 字符级兜底
]


def _token_length(text: str) -> int:
    """
    计算文本的 token 数量（使用 cl100k_base BPE 编码器）。

    作为 RecursiveCharacterTextSplitter 的 length_function，
    确保分块大小以 token 为单位而非字符数，
    与 OpenAI Embedding API 的 token 限制保持一致。

    参数:
        text: 待计算的任意文本片段。

    返回:
        整数 token 数量。
    """
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return len(_ENCODER.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[str]:
    """
    对文本执行递归语义分块，返回文本块列表。

    采用 LangChain RecursiveCharacterTextSplitter + tiktoken 长度函数：
      - 优先在段落/句末等高语义权重位置断开；
      - 相邻块之间保留 chunk_overlap token 的重叠，确保跨块语义连贯性；
      - 空块（清洗或分割后产生的空字符串）自动过滤。

    参数:
        text:           已清洗的纯文本。
        chunk_size:     每块最大 token 数，默认 512。
        chunk_overlap:  相邻块的 token 重叠量，默认 64。

    返回:
        非空文本块的字符串列表，长度 >= 1。
        若输入文本为空，返回空列表 []。
    """
    if not text or not text.strip():
        return []

    # 文本切割器
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_token_length,
        separators=_CHINESE_SEPARATORS,
        keep_separator=True,
    )

    raw_chunks = splitter.split_text(text)
    # 过滤空块，去除仅含空白的碎片
    return [c.strip() for c in raw_chunks if c.strip()]


def count_tokens(text: str) -> int:
    """
    对外暴露的 token 计数工具函数。

    供其他模块（如 indexer）在分块前快速估算文本大小，
    无需直接依赖 tiktoken。

    参数:
        text: 任意文本。

    返回:
        token 数量（整数）。
    """
    return _token_length(text)
