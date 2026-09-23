"""验证个人资料 RAG 工具的可观测降级行为。"""

import asyncio

from app.services import rag_chain


def test_search_tool_returns_empty_result_as_observation(monkeypatch) -> None:
    """测试：个人资料未命中时，工具返回 fallback Observation 而不是抛出异常。"""
    async def fake_embed_query(_query: str) -> list[float]:
        return [0.1, 0.2]

    async def fake_search_by_user(**_kwargs) -> list[object]:
        return []

    monkeypatch.setattr(rag_chain, "embed_query", fake_embed_query)
    monkeypatch.setattr(rag_chain, "search_by_user", fake_search_by_user)
    observations: list[dict[str, str]] = []
    tool = rag_chain._make_search_tool("user-a", [], observations)

    result = asyncio.run(tool.ainvoke({"query": "当前日程"}))

    assert "暂无与此问题相关" in result
    assert observations == [{
        "type": "tool.completed",
        "tool": "search_personal_knowledge",
        "label": "个人资料中未找到相关内容，已转用通用旅行知识",
    }]


def test_search_tool_returns_failure_as_debuggable_observation(monkeypatch) -> None:
    """测试：检索依赖异常时，工具返回 fallback 并保留公开调试摘要。"""
    async def failing_embed_query(_query: str) -> list[float]:
        raise ValueError("Embedding 维度不匹配：当前模型返回 1024 维")

    monkeypatch.setattr(rag_chain, "embed_query", failing_embed_query)
    observations: list[dict[str, str]] = []
    tool = rag_chain._make_search_tool("user-a", [], observations)

    result = asyncio.run(tool.ainvoke({"query": "当前日程"}))

    assert "暂时不可用" in result
    assert observations[0]["type"] == "tool.failed"
    assert observations[0]["tool"] == "search_personal_knowledge"
    assert "Embedding 维度不匹配" in observations[0]["debug"]
