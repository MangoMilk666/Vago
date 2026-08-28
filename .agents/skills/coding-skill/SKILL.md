---
name: vago-coding-skill
description: Vago 项目的编码规范。仅在用户明确要求新增、修改、删除、重构或修复代码时使用；仅进行代码分析、解释或 Review 且未要求更改时不得调用。
---

# Vago Coding Skill

## Scope

本 Skill 仅负责 Vago 项目的**代码修改规范**。

涉及产品定位、功能取舍、架构迁移或技术栈决策时，应同时参考 `project-remould-skill`，并以其中的项目级约束为准。

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

避免：

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