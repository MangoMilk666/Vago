"""
LLM 工厂模块（LLM Factory）。

封装 ChatOpenAI 客户端的创建逻辑，提供统一的 LLM 实例获取接口。
通过配置 base_url + api_key，支持任何 OpenAI Chat Completions 兼容接口：
  - OpenAI 官方：gpt-4o / gpt-4o-mini
  - 阿里云百炼（DashScope）：qwen-plus / qwen-turbo / qwen-max
  - DeepSeek：deepseek-chat / deepseek-reasoner
  - 其他 OpenAI 兼容 Provider

LangChain ChatOpenAI 通过 base_url 参数指向目标端点，
api_key 透传给底层 OpenAI SDK，无需额外适配代码。
"""

import logging

from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


def get_chat_llm(streaming: bool = False) -> ChatOpenAI:
    """
    创建并返回一个配置好的 ChatOpenAI 实例。

    所有参数均从 Settings 读取，支持通过环境变量在不同 Provider 间切换，
    无需修改代码。streaming=True 时启用流式输出，供 SSE 端点使用。

    参数:
        streaming: 是否启用 token 级流式输出。
                   True  → 搭配 astream / astream_events 使用；
                   False → 搭配 ainvoke 使用，返回完整响应。

    返回:
        ChatOpenAI 实例，已配置 api_key、base_url、model、temperature、max_tokens。

    注意:
        - 每次调用均返回新实例，避免 streaming 状态在并发请求间共享；
        - base_url 为 None 时 LangChain 使用 OpenAI 官方端点（https://api.openai.com/v1）。
    """
    api_key = settings.get_llm_api_key()
    base_url = settings.get_llm_base_url()

    if not api_key:
        logger.warning("[llm] LLM API Key 未配置，LLM 调用将失败")

    logger.debug(
        "[llm] 创建 ChatOpenAI model=%s base_url=%s streaming=%s",
        settings.llm_model,
        base_url or "OpenAI 默认",
        streaming,
    )
    # OpenAI SDK 的 extra_body 设计
    # 在官方 openai 库中，client.chat.completions.create 方法提供了一个特殊的参数 extra_body（类型为 dict）。
    # 任何放进 extra_body 的键值对，都会被原样合并到最终发送给服务端的 JSON 请求体根节点中。

    model_kwargs = {}
    if not streaming and base_url and "aliyuncs.com" in base_url:
        model_kwargs["extra_body"] = {"enable_thinking": False} # 最终发送给阿里云的 HTTP 请求体中

    # LangChain 的 model_kwargs 传递通道
    # LangChain 的 ChatOpenAI 构造函数中，model_kwargs 字典中包含的所有内容，都会在运行时原封不动地透传给底层的 OpenAI SDK 调用。
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model_name=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=streaming,
        model_kwargs=model_kwargs,
    )
