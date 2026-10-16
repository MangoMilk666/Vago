---
name: vago-coding-skill
description: Vago 项目的编码规范。仅在用户明确要求新增、修改、删除、重构或修复代码时使用；仅进行代码分析、解释或 Review 且未要求更改时不得调用。
---

# Vago Coding Skill

## Scope

本 Skill 仅负责 Vago 项目的**代码编码规范**。

涉及产品定位、功能取舍、架构迁移或技术栈决策时，应同时参考项目长期skill `vago-project-skill`, `readme.md`文档，架构文档`architecture.md`, 需求文档`PRD.md`；涉及到不同模块（比如ios客户端）的开发，需要参考对应的设计文档和开发计划文档。

## Trigger Rules

仅当用户明确要求实际修改代码时调用本 Skill，例如：

- 实现 / 新增功能；
- 修改现有实现；
- 修复 Bug；
- 重构代码；
- 删除或替换代码。

以下情况**不得仅因为涉及代码而自动调用**：

- 解释代码；
- 分析实现；
- Code Review；
- 讨论设计方案；
- 查询问题原因；
- 提出修改建议。

如果用户先要求 Review，只有在随后明确要求“修改 / 帮我改 / implement / fix / refactor”等实际变更时，才进入本 Skill。

## Comment Rules

所有新增或修改的代码，应在有助于理解业务逻辑、关键流程、复杂判断或非显然实现的位置添加**必要的中文注释**。

避免做：

- 更改已经存在的注释，除非出现与最新代码逻辑不符合的严重逻辑错误，或者根据最新标准进行旧注释修正。

- 给显而易见的代码逐行加注释；
- 用注释重复代码本身；
- 为了满足注释要求而制造无意义注释。

### Python

短注释使用：

```python
# 中文短注释
```

较长的说明使用：

```python
'''
中文长注释。
用于解释复杂流程、模块职责或需要整体说明的实现。
'''
```

具体场景的注释规范：

- 对于`if-else`分支代码: 注释统一写成`如果+<具体条件>`的形式
- 对于返回值类型为`bool(ean)`类型的函数，注释应统一写成`判断xxx是否xxx`的“陈述疑问句”形式。
- 对于单元测试，注释时要标注`测试：xxx`

```python
# 如果用户授权了xxx, xxx
if user_allow:
    do something
def test_something_work:
    '''
    测试：xxx逻辑是否生效
    '''
    xxx
def need_current_trip(xxx) -> bool:
    '''
    判断是否需要使用current_trip上下文信息。
    '''
    xxx
    
```

### Other Languages

TypeScript / JavaScript / Swift 等语言使用该语言原生合法的注释语法，并保持中文说明：

```typescript
// 中文短注释

/*
 * 中文长注释
 */
```

```swift
// 中文短注释

/*
 中文长注释
 */
```

不得为了统一形式而使用目标语言不支持的注释语法。

除了语法，注释要求基本和Python语言对齐。

### 正面/反面例子

以下是一个反面例子，注释逻辑混乱，让人无法看懂。

```python
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
```

经过修改，以下是一个正面例子:

```python
"""规划候选的 API 请求与响应模型"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class ProposalCreateRequest(BaseModel):
    """候选plan创建DTO类。
    完整保留 brief/候选 JSON数据；
    后续阶段 3 会增加确定性时间线校验。
    brief 保存规划目标与约束，content 保存地点、路线等候选方案内容。"""

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
    """候选计划总结信息类。
    列表项不加载大体量地点与路线内容。"""

    model_config = ConfigDict(populate_by_name=True)

    uuid: str
    conversation_uuid: str = Field(alias="conversationUuid")
    version: int
    target_kind: str = Field(alias="targetKind")
    target_plan_uuid: str | None = Field(alias="targetPlanUuid")
    status: str
    created_at: datetime = Field(alias="createdAt")


class ProposalDetail(ProposalSummary):
    """候选计划细节类。
    包含可回读的完整候选计划信息；
    不含内部幂等键与请求指纹。"""

    target_plan_updated_at: datetime | None = Field(alias="targetPlanUpdatedAt")
    brief: dict[str, Any]
    content: dict[str, Any]


class ProposalStatus(BaseModel):
    """候选计划状态类。
    供刷新或事件断线后查询的持久化状态。"""

    uuid: str
    version: int
    status: str
```



## Change Principles

修改代码时：

1. 优先遵循现有项目结构与编码风格；
2. 避免与当前任务无关的顺手重构；
3. 不为了展示技术而增加额外抽象或依赖；
4. 修改公共 API、数据模型或跨模块接口时检查调用方影响；
5. 与 remould 方向发生冲突时，以 `project-remould-skill` 为准；
6. 保持改动范围清晰、可验证、便于提交。

## Git Commit Message

每次实际完成代码更改后，最终回复中必须包含一个推荐的 Git commit message。

格式：

```text
type(xx): 中文描述
```

要求：

- commit message 使用中文；
- 描述本次实际完成的主要变更；
- 简洁，不罗列实现细节。

推荐 type：

```text
feat     新功能
fix      Bug 修复
refactor 重构
docs     文档
test     测试
chore    工程或配置调整
style    不影响逻辑的代码风格修改
```

`xx` 表示本次修改涉及的模块，例如：

```text
feat(auth): 增加 FastAPI 用户登录接口
refactor(rag): 调整个性化上下文检索流程
fix(trip): 修复行程日期更新异常
feat(ios): 增加行程列表页面
```

## Response Requirement

完成实际代码修改后，回复至少包含：

- 本次修改的简要说明；
- 必要的验证 / 测试结果；
- 推荐 Git commit message。

仅进行分析或 Review、没有实际修改代码时，不生成 commit message。