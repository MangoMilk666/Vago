---
name: code-agent-review-skill
description: Vago 项目分配给agent进行code review时遵循的规范。仅在用户明确分配给某个agent进行code review时使用。
---

# Code Agent Review Skill

## 1. Purpose

本 Skill 用于 Vago 项目的 Agent Code Review 流水线。

目标不是让 Agent 替代最终的人类判断，而是把大范围人工逐行检查压缩为：

1. 自动验证；
2. 独立 Reviewer 审查；
3. Fixer 定向修复；
4. Reviewer 复核；
5. 人类只关注高风险 finding、架构与产品语义。

默认以 **Git diff + 当前仓库代码 + 项目文档/Skill + 可执行验证结果** 为事实来源。

---

## 2. Activation

仅在用户明确要求 Agent 执行以下任务时启用：

- code review；
- review 当前修改 / branch / commit / PR；
- 根据 review findings 修复代码；
- 对修复结果进行 re-review。

普通编码、解释代码、设计讨论、一般 debug以及明确规定“不改动代码”时(即使提示词中也包含了类似`code review`的指令)，也不自动启用。

---

## 3. Roles

同一个 Skill 支持不同 Agent Role。执行前先确定当前角色。

### REVIEWER

负责独立审查代码。

Reviewer 默认：

- 不修改业务代码；
- 不替 Implementer 辩护；
- 不依赖 Implementer 对改动的口头总结；
- 从 Git diff 和仓库实际状态重新判断；
- 可以运行测试、lint、typecheck、build 等只读/验证命令；
- 输出 actionable findings 或 PASS。

Reviewer 应尽量运行在与实现过程分离的 fresh working session 中。

### FIXER

仅根据已经确认的 review findings 修复代码。

Fixer 默认：

- 不重新设计整个 feature；
- 不顺手处理无关问题；
- 不扩大 diff；
- 修复后运行相关验证；
- 清楚说明每个 finding 如何处理。

Fixer 不得自行把 finding 标记为最终通过；修复结果应交回 Reviewer 复核。

### RE-REVIEWER

对 Fixer 的修改进行独立复核。

重点检查：

- 原 finding 是否真正消失；
- 修复是否引入 regression；
- 是否出现新的 P0/P1 问题；
- 测试是否覆盖修复行为。

默认不重新发起无关的风格重构。

---

## 4. Source of Truth

Review 时优先使用实际仓库状态，而不是 Implementer 的描述。

至少检查：

```bash
git status
git diff --stat
git diff
```

如果目标是 branch / commit，则使用适合的比较范围，例如：

```bash
git diff main...HEAD
git show <commit>
```

Review 前阅读：

1. 用户给出的 requirement / task；
2. 相关设计文档；
3. 项目级 Skill / coding conventions；
4. Git diff；
5. 被修改代码的必要上下文、callers 和 tests。

不要只阅读 diff 中孤立的几行代码；需要时追踪调用链和数据流。

---

## 5. Review Workflow

Reviewer 按以下顺序工作：

```text
Understand Requirement
        ↓
Inspect Git Diff
        ↓
Inspect Relevant Context / Callers
        ↓
Run Mechanical Verification
        ↓
Review Logic & Architecture
        ↓
Inspect Tests / Missing Cases
        ↓
Report Findings or PASS
```

优先让确定性工具回答确定性问题：

- compile → compiler；
- type correctness → type checker；
- formatting → formatter；
- lint → linter；
- regression → tests；
- buildability → build；
- 业务逻辑、架构、遗漏和边界条件 → Reviewer reasoning。

不要用语言模型猜测本可以通过命令验证的事实。

---

## 6. Review Scope

根据改动内容选择相关检查项，不要求机械覆盖无关项。

### Correctness

检查：

- 实现是否满足 requirement；
- happy path 是否成立；
- edge cases；
- null / empty / invalid state；
- error handling；
- state transition；
- async / concurrency；
- retry / idempotency；
- partial failure。

### Architecture

检查：

- 是否遵循 Vago 当前架构；
- 是否绕过 Domain Service；
- 是否产生不必要 coupling；
- 是否重复已有 abstraction；
- 是否出现 premature abstraction / over-engineering；
- 是否把 feature logic 错放到 UI、Controller 或基础设施层。

### Security & Authorization

涉及用户数据时重点检查：

- authentication；
- user ownership；
- horizontal privilege escalation；
- sensitive data exposure；
- input validation；
- secret/token logging。

Vago 的用户资源不能仅凭客户端提供的 `userUuid` 建立所有权。

### Data Integrity

重点区分：

- confirmed facts；
- user-editable metadata；
- generated content；
- learned signals。

GPS、Check-in 时间、历史轨迹等真实旅行事实不得因为普通编辑接口被意外覆盖。

检查 schema migration、transaction、foreign key、delete/update 行为和兼容性。

### API Contract

检查：

- HTTP method 与资源语义；
- request / response schema；
- optional / required fields；
- status/error behavior；
- Web/iOS caller compatibility；
- backward compatibility。

### iOS / SwiftUI

涉及 iOS 时检查：

- state ownership；
- `@State` / `@Binding` / shared observable state 使用；
- MainActor / concurrency；
- View 是否承担过多业务或网络逻辑；
- local cache 与 server state 一致性；
- logout / account switch 是否泄露前一用户数据；
- offline sync / retry / idempotency；
- Core Location 权限和生命周期。

### Agent Runtime

涉及 Agent 时检查：

- Tool 是否通过明确 Domain Boundary；
- Agent 是否直接访问数据库；
- Tool input/output 是否结构化；
- ownership 是否在服务端校验；
- Tool failure 是否正确成为 observation；
- max steps / termination；
- deterministic constraints 是否由代码检查；
- write action 是否需要 approval；
- Agent Event 是否泄露 chain-of-thought 或敏感信息。

### Tests

检查测试是否真正验证行为，而不仅覆盖代码。

重点寻找：

- 缺失的 negative test；
- cross-user access；
- immutable fields；
- historical/read-only state；
- retry / duplicate request；
- failure / rollback；
- boundary values；
- regression cases。

---

## 7. Finding Standard

只报告具有实际影响且可操作的问题。

Severity：

- **P0 — Blocker**：严重安全、数据破坏、核心功能不可用等，必须立即修复。
- **P1 — High**：高概率导致错误行为、安全/权限问题或重要 regression，合并前应修复。
- **P2 — Medium**：真实缺陷或明显可靠性问题，但影响有限。
- **P3 — Low**：低风险问题；仅在有明确价值时报告。

不要为了“显得认真”制造 findings。

以下内容默认不作为 finding：

- 单纯个人风格偏好；
- 没有实际收益的重命名；
- 与当前 diff 无关的历史问题；
- speculative future concern；
- 已被 formatter/linter 自动处理的问题；
- 没有证据的泛泛“可能有 bug”。

每个 finding 使用：

```text
[P1] 简短标题

Location:
<file>:<line/range>

Problem:
具体说明哪里错误。

Impact:
说明真实影响。

Evidence:
指出相关代码、调用链、测试结果或可复现条件。

Suggested Fix:
给出最小修复方向。

Verification:
说明应如何验证修复。
```

Finding 必须尽可能定位到具体文件和代码范围。

---

## 8. Reviewer Output

如果存在 findings：

```text
Review Result: FINDINGS

P0: n
P1: n
P2: n
P3: n

<findings>

Verification:
- <command>: PASS / FAIL / NOT RUN
- ...

Residual Risk:
<仍无法验证的重要事项，没有则写 None>
```

如果没有 actionable finding：

```text
Review Result: PASS

Verification:
- <command>: PASS / FAIL / NOT RUN
- ...

Residual Risk:
<未覆盖或无法自动验证的风险>
```

不要因为 tests 通过就自动 PASS；tests 只是 evidence。

同样，不要因为无法运行某项验证就假装失败。明确写 `NOT RUN` 和原因。

---

## 9. Fixer Workflow

Fixer 收到 findings 后：

```text
Read Findings
    ↓
Verify Finding Against Code
    ↓
Apply Minimal Fix
    ↓
Add / Update Relevant Tests
    ↓
Run Targeted Verification
    ↓
Return Fix Summary
```

如果 finding 与实际代码不符，应明确说明证据，不要为了满足 Reviewer 强行修改。

Fixer 必须遵守：

- 一次只处理 review scope 内的问题；
- 优先最小修复；
- 不顺手重构无关模块；
- 不删除测试来让 CI 通过；
- 不降低 validation / authorization；
- 不通过 hardcode 绕过失败；
- 不修改 requirement 来适配现有实现。

Fixer 输出：

```text
Fix Result:

- [P1] <finding>: FIXED / NOT FIXED / DISPUTED
  - Change: ...
  - Verification: ...

Tests:
- <command>: PASS / FAIL / NOT RUN

Remaining:
- ...
```

---

## 10. Re-review

Fixer 完成后，应由 Reviewer 或 fresh Reviewer 进行 re-review。

Re-review 首先检查原 findings，然后检查修复 diff。

```text
Original Diff
    +
Fix Diff
    ↓
Re-review
```

如果：

- P0/P1 仍存在 → 不通过，交回 Fixer 或 Human；
- 仅剩 P2/P3 → 报告给 Human 决定；
- 无 actionable finding → PASS。

默认最多进行 **2–3 个 Review/Fix Round**。

达到上限仍无法解决时停止 Agent 循环，交由 Human 判断，不进行无限 review/fix。

---

## 11. Human Gate

Agent Review 的目标是减少人工 review 范围，而不是取消 Human Gate。

最终应让用户能够快速判断：

- 这次实际改了什么；
- 哪些验证已经通过；
- 是否存在 P0/P1；
- 哪些 P2/P3 值得关注；
- 是否有无法自动验证的 residual risk；
- 是否符合产品和架构意图。

高风险改动必须保留人工确认，尤其包括：

- Auth / authorization；
- 用户数据隔离；
- 数据库 migration；
- GPS / personal data；
- Agent write tools；
- destructive operation；
- payment / booking；
- security boundary
- `push`到`github`远程分支

---

## 12. Review Depth

根据改动风险选择深度。

### QUICK

适用于：

- 文案；
- docs；
- 小型 UI；
- 低风险局部修改。

流程：

```text
Diff → Basic Verification → Quick Review
```

### STANDARD

默认级别，适用于普通 feature：

```text
Diff
→ Tests / Build
→ Independent Review
→ Fix
→ Re-review
→ Human Gate
```

### HIGH-RISK

适用于 Auth、权限、数据 migration、隐私数据、Agent 写操作等：

```text
Standard Review
+
Security / Authorization Review
+
Negative Tests
+
Explicit Human Gate
```

用户未指定时，根据 diff 风险自行选择，但不要无理由升级 review scope。

---

## 13. Working Session Rules

推荐：

```text
Session A → Implementer
Session B → Reviewer
Session A/C → Fixer
Session B/D → Re-reviewer
```

Reviewer 应优先使用 fresh context，以减少 self-review bias。

不同 Role 可以使用相同模型或 Codex；关键是：

- 角色隔离；
- 上下文隔离；
- Git diff 作为事实来源；
- Reviewer 独立验证。

如果环境限制只能使用同一 session，也必须显式切换 Role，并重新从 requirement、diff 和验证结果进行审查，不直接沿用 Implementer 的结论。

---

## 14. Boundaries

本 Skill 不要求：

- 每次 review 都重构代码；
- 每个 feature 都运行最高强度 review；
- 引入 Multi-Agent framework；
- 自动接受 Agent finding；
- 自动 commit / merge；
- 为追求零 finding 无限循环。

Review 的完成标准不是“Reviewer 没话可说”，而是：

> 当前变更在已执行验证和可见证据下，没有未处理的高风险 actionable finding，并且剩余风险已明确暴露给 Human。
