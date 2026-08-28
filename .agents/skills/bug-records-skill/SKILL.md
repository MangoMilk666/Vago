---
name: bug-records-skill
description: 用于在项目根目录的bug-records.md中按照统一格式记录技术问题，包含背景、问题、原因、解决方案，适用于面试素材沉淀与工程复盘。
---
# Bug Records Skill

## 技能描述

本技能用于在项目根目录下的 `bug-records.md` 文件中，按照统一格式记录工程调试过程中遇到的技术问题（Bug）。每条记录包含背景、问题表现、原因分析、解决方案四个部分，适用于技术复盘、知识沉淀及面试准备。

## 触发方式

- 用户明确要求记录一个 bug（如：“帮我把这个 bug 记录到 bug-records.md”）
- 用户在解决完一个技术问题后，要求生成 bug 复盘文档
- 在代码审查或调试会话结束时，主动询问是否需要归档

## 记录追加规则

1. **文件位置**：项目根目录下的 `bug-records.md`。若文件不存在，则创建。
2. **追加方式**：在文件末尾追加新记录，不覆盖已有内容。
3. **记录顺序**：按时间倒序排列（最新的在最上面），或按用户要求。若未特别说明，默认追加到末尾（正序）。
4. **分隔符**：每条记录之间使用 `---` 分隔线隔开。

## 记录格式模板

每条记录必须严格遵循以下 Markdown 结构：

```markdown
# [Bug Record] {简短标题，突出核心问题}

**Time:** {YYYY-MM-DD} (可选添加 -- HH:MM)

## 背景（Background）

{描述业务场景、技术栈、调用链路、上下文信息。2-5 句话交代清楚}

## 问题表现（Problem / Symptoms）

{描述用户看到的错误现象、异常行为、日志输出、监控指标等。强调“现象的反常性”}

## 问题原因分析（Root Cause Analysis）

{根本原因：哪一层、哪个组件、哪个逻辑导致。可以包含数据流格式差异、并发问题、配置错误等。适当使用代码片段说明}

## 解决方案（Final Solution）

{具体的修复代码或配置变更。强调“一行改动”或最小化改动。同时给出预防性建议}
```

## 内容写作建议（供 agent 参考）

为提升面试素材价值，每条记录应尽量包含以下要素：

- **背景**：突出技术栈（如 Spring Boot + React）、调用链路（前端 → 代理 → Java → Python），让面试官快速理解上下文。
- **问题表现**：制造“反差感”——例如“Chrome DevTools 能看到 SSE 事件，但页面无任何文字”。
- **原因分析**：剖析深层格式差异、协议规范细节（如 RFC 8895 空格可选）、各组件实现差异。
- **解决方案**：展示精确的代码改动（如 `slice(5).trim()`），并提炼通用教训（如“手动解析协议时不要假设可选字符”）。
- **可选扩展**：在解决方案后增加“面试表达建议”小节，提供讲故事的要点。

## 示例（基于真实案例）

```markdown
# [Bug Record] SSE 流式 AI 回答前端完全不可见：Spring SseEmitter 与手动 SSE 解析格式不匹配

**Time:** 2026-05-29

## 背景（Background）

项目 Vago（叠迹），Java（Spring Boot 3.x）+ Python（FastAPI）混合架构。Java 代理 Python 的 LLM SSE 流，通过 SseEmitter 推送给 React 前端。前端使用 fetch + ReadableStream 手动解析 SSE（因需要 POST + JWT）。

## 问题表现（Problem / Symptoms）

用户发送消息后，AI 气泡显示加载动画，随后动画消失但气泡空白。Chrome DevTools 中 EventStream 子标签能清晰看到 token 流入，但页面毫无更新。

## 问题原因分析（Root Cause Analysis）

Python 生成的 SSE 格式为 `data: {"type":"text"}\n\n`（有空格），Spring 的 `SseEmitter` 输出为 `data:{"type":"text"}\n\n`（无空格）。前端解析代码使用 `line.startsWith('data: ')` 判断，导致所有事件被 `continue` 跳过，且无任何异常。React 状态未更新，最终渲染 `null`。

## 解决方案（Final Solution）

修改前端解析逻辑：`if (!line.startsWith('data:')) continue; const raw = line.slice(5).trim();`。兼容有无空格，符合 SSE 规范（RFC 8895 允许空格可选）。
```

## 使用说明

当用户要求记录 bug 时，请按以下步骤操作：

1. 询问或确认 bug 的标题、发生时间。
2. 引导用户提供背景、问题现象、分析过程和解决方案（可通过对话逐步收集）。
3. 按照上述模板生成完整的 Markdown 记录。
4. 检查 `bug-records.md` 是否存在于项目根目录，若不存在则创建。
5. 将新记录追加到文件末尾（或按用户要求插入到开头）。
6. 输出确认信息：“已记录 bug 到 bug-records.md”。

## 注意事项

- 不要覆盖已有记录，只追加。
- 如果用户提供的信息不完整，应主动提问补齐（例如：“能否描述一下当时的调用链路？”）。
- 记录中的代码片段尽量保持精简，突出关键差异点。
- 若 bug 涉及敏感信息（如密钥、IP），需做脱敏处理。