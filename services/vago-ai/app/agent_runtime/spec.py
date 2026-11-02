'''对应 graph.py 初始化时使用的 Agent 配置，重点看工具白名单、步数和超时。'''
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent_runtime.registry import ToolRegistry


class AgentSpec(BaseModel):
    """约束一个 Agent 的工具范围和单轮资源上限。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    allowed_tools: frozenset[str]
    max_read_steps: int = Field(default=6, ge=1, le=12)
    max_model_steps: int = Field(default=3, ge=1, le=8)
    timeout_seconds: int = Field(default=120, ge=5, le=300)

    @model_validator(mode="after")
    def check_role(self) -> "AgentSpec":
        """判断主规划 Agent 是否拥有明确工具范围。"""
        if self.role == "planner" and not self.allowed_tools:
            raise ValueError("规划 Agent 的工具白名单不能为空")
        return self


class AgentTask(BaseModel):
    """未来域 Agent 的结构化任务输入；本阶段只固定边界。"""

    model_config = ConfigDict(extra="forbid")

    task_uuid: str = Field(min_length=32, max_length=32)
    user_uuid: str = Field(min_length=32)
    conversation_uuid: str = Field(min_length=32, max_length=32)
    goal: str = Field(min_length=1)
    role: str
    allowed_tools: frozenset[str]


class AgentReport(BaseModel):
    """未来域 Agent 的结构化回报；证据与未解决项不能藏在自由文本里。"""

    model_config = ConfigDict(extra="forbid")

    task_uuid: str
    status: Literal["completed", "clarification", "failed", "cancelled"]
    summary: str
    resource_ids: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class AgentSpecRegistry:
    """启动时核对配置与真实 Domain Tools，拒绝不存在的工具名。"""

    def __init__(self, specs: list[AgentSpec], tools: ToolRegistry) -> None:
        self._specs: dict[str, AgentSpec] = {}
        for spec in specs:
            if spec.role in self._specs:
                raise ValueError(f"重复的 Agent 角色：{spec.role}")
            unknown = spec.allowed_tools - (tools.names | {"search_personal_knowledge"})
            if unknown:
                raise ValueError(f"{spec.role} 使用了未注册工具：{', '.join(sorted(unknown))}")
            self._specs[spec.role] = spec

    def get(self, role: str) -> AgentSpec:
        """读取指定 Agent 配置；未知角色不得退回为无限权限。"""
        return self._specs[role]


def planner_spec(tools: ToolRegistry) -> AgentSpec:
    """创建单 Agent 规划配置，权限仅覆盖已注册的只读领域工具。"""
    return AgentSpec(
        role="planner",
        description="读取授权的个人旅行事实，协调规划并生成待用户确认的候选。",
        allowed_tools=tools.names | {"search_personal_knowledge"},
    )
