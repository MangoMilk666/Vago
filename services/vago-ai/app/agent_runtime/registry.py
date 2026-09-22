"""Agent 可调用内部领域工具的注册表，不直接暴露数据库能力。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AgentTool:
    """描述一个内部只读工具及其面向用户的执行提示。"""

    name: str
    label: str
    handler: Callable[[Session, str, dict[str, Any]], dict[str, Any] | None]


class ToolRegistry:
    """集中管理 Runtime 可调用的内部领域工具，避免 Runtime 出现工具名分支。"""

    def __init__(self, tools: list[AgentTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> AgentTool:
        """按稳定工具名读取定义，不存在时显式报错以避免静默跳过。"""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"未注册的 Agent 工具：{name}") from exc
