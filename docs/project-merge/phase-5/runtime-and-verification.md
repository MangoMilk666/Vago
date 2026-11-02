# 阶段 5：LangGraph 单 Agent 规划

## 已接入

- 流式 `/api/v1/ai/chat/stream` 使用 LangGraph 串联工具选择、领域资料读取、澄清、LangChain 回答与候选保存。原有认证、Domain Tools、RAG 和 SSE 文本格式仍由现有服务承担。
- `AgentSpec` 固定角色、工具白名单、读取步数、模型步数和超时；`AgentTask`、`AgentReport` 是后续域 Agent 的输入输出契约，本阶段不执行委派。
- 单轮公开事件附带 `turnUuid`、`conversationUuid`、`sequence`；已有会话消息保存公开事件。客户端断开流时取消图任务，并在会话中记录取消终态。
- 结构化计划只有日期和每日安排齐全才尝试建立候选。候选仍须通过阶段 3 的确定性校验；缺少地点来源、坐标或路线证据时不得据此直接确认正式计划。

## 已验证与边界

- `test_planning_graph.py`、`test_chat_context_api.py`、`test_agent_runtime.py`、`test_agent_tool_selection.py`、`test_rag_chain.py`、`test_plan_proposals_api.py` 共 42 项通过；本机 MySQL 候选集成测试 2 项通过；`git diff --check` 通过。
- 真实模型参与的多轮澄清到候选保存、断线重连及双用户隔离尚未完成端到端验收。非流式 `/api/v1/ai/chat` 仍走原有实现。
- 候选自动转换当前使用中国大陆规划的 `Asia/Shanghai` 时区；其他地区不能据此声称时间线已经核验。阶段 5 的正式完成需补真实场景验收并处理这条边界。
