# FastAPI API 文档

**状态：当前接口索引。** 所有路径均在 `/api/v1` 下，具体请求字段、响应模型和验证约束以 `services/vago-ai/app` 中的路由与 Pydantic schema 为准；运行服务时可查看 FastAPI `/docs` 生成的 OpenAPI。领域文档解释业务边界，不复制全部自动生成的字段表。

| 领域 | 文档 | 代码入口 |
| --- | --- | --- |
| 认证与用户 | [user-service.md](user-service.md) | `app/auth/router.py`、`app/users/router.py`、`app/preferences/router.py` |
| Plan / Trip / Itinerary | [travel-service.md](travel-service.md) | `app/travel/router.py` |
| Personal Knowledge | [knowledge-service.md](knowledge-service.md) | `app/knowledge/router.py` |
| Travel Observations | [footprint-service.md](footprint-service.md) | `app/footprints/router.py` |

Agent、Memory、Personal Context 与 AI 路由也已在 `app/api/v1.py` 注册；这些能力的现状与目标边界见 [Agent Runtime 设计](../modules/agent/agent-runtime.md)。此目录不暗示每个已注册路由都具备完整目标 Agent 能力。
