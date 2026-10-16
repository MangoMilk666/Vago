"""候选创建与回读的 API 契约。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class ProposalCreateRequest(BaseModel):
    """完整保留 brief/候选 JSON；阶段 3 再增加确定性时间线校验。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)
    target_kind: Literal["new_plan", "draft_plan"] = Field(alias="targetKind")
    target_plan_uuid: str | None = Field(default=None, alias="targetPlanUuid", min_length=32, max_length=32)
    brief: dict[str, Any]
    content: dict[str, Any]

    @model_validator(mode="after")
    def validate_target(self) -> "ProposalCreateRequest":
        """判断目标类型与目标 Plan UUID 是否相互匹配。"""
        # 如果是编辑草稿，必须明确指定已有 Plan；新建则不得附带 Plan UUID。
        if (self.target_kind == "draft_plan") != (self.target_plan_uuid is not None):
            raise PydanticCustomError("proposal_target_invalid", "草稿编辑必须指定 targetPlanUuid，新建计划不得指定")
        # 如果幂等键全是空白，拒绝产生无法可靠重试的提交。
        if not self.idempotency_key.strip():
            raise PydanticCustomError("proposal_key_blank", "idempotencyKey 不能为空白")
        return self


class ProposalSummary(BaseModel):
    """列表项不加载大体量地点与路线内容。"""

    model_config = ConfigDict(populate_by_name=True)

    uuid: str
    conversation_uuid: str = Field(alias="conversationUuid")
    version: int
    target_kind: str = Field(alias="targetKind")
    target_plan_uuid: str | None = Field(alias="targetPlanUuid")
    status: str
    created_at: datetime = Field(alias="createdAt")


class ProposalDetail(ProposalSummary):
    """可回读的完整候选；不含内部幂等键与请求指纹。"""

    target_plan_updated_at: datetime | None = Field(alias="targetPlanUpdatedAt")
    brief: dict[str, Any]
    content: dict[str, Any]


class ProposalStatus(BaseModel):
    """供刷新或事件断线后查询的持久化状态。"""

    uuid: str
    version: int
    status: str
