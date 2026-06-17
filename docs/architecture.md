# 项目架构

> 最后更新：2026-06-17｜架构：混合单体（Java CRUD + Python AI）

---

## 当前实现状态

| 模块 | 路径 | 状态 | 说明 |
|------|------|------|------|
| vago-backend | `services/vago-backend/` | ✅ 完成 | Java Spring Boot 单体，端口 8080 |
| vago-ai | `services/vago-ai/` | ✅ 完成 | Python FastAPI AI 服务，端口 8000 |
| vago-web | `apps/vago-web/` | ✅ 完成 | React + Vite 前端，端口 5173 |
| ~~vago-gateway~~ | `services/vago-gateway/` | ⛔ 已废弃 | 单体架构不需要网关，目录保留 |
| ~~vago-service-user~~ | `services/vago-service-user/` | ⛔ 已废弃 | 代码已迁入 vago-backend，目录保留 |

---

## 架构演进历史

```
v0.1（初始微服务）：
  vago-gateway:8080 → vago-service-user:8081
  Java SSE 代理 → Python AI（两跳延迟）

v0.2（当前 · 混合单体，2026-05 重构）：
  vago-backend:8080  ← 所有 CRUD + auth
  vago-ai:8000       ← AI 对话（前端直连，消除 Java SSE 代理）
```

**核心重构**（2026-06）：AI 对话接口（chat / chat/stream）从前端 → Java → Python 的三跳链路，
改为前端 → Python 直连，消除 Java SSE 代理，降低延迟和连接管理复杂度。

---

## 总目录

```
Vago/
├── apps/
│   └── vago-web/               # ✅ React 18 + Vite 5 + Tailwind CSS
│       ├── src/
│       │   ├── api/ai.js           # AI chat SSE + save draft/trip
│       │   ├── api/travel.js       # Guide/Trip/Plan CRUD
│       │   ├── api/user.js         # 用户认证
│       │   ├── pages/AiPlanPage.jsx# 攻略库 + AI 对话（双栏布局）
│       │   ├── pages/GuidePage.jsx # 攻略库管理
│       │   ├── pages/PlanPage.jsx  # 计划列表
│       │   ├── pages/TripPage.jsx  # 行程列表
│       │   ├── pages/ItineraryPage.jsx # 每日行程编辑
│       │   ├── stores/auth.js      # localStorage 认证状态
│       │   └── App.jsx             # React Router v6
│       └── vite.config.js      # 代理：/api/v1/ai/chat → :8000，其余 /api/v1 → :8080
│
├── services/
│   ├── pom.xml                 # Maven 父 POM（只构建 vago-backend）
│   │
│   ├── vago-backend/           # ✅ Java 单体后端（Spring Boot 3.2.5，:8080）
│   │   └── src/main/java/com/vago/
│   │       ├── VagoApplication.java           # 主类，@MapperScan
│   │       ├── common/                        # Result.java, ResultCode.java, PageVO.java
│   │       ├── config/                        # WebMvc, Swagger, AiClient
│   │       ├── constant/ context/ exception/ handler/ interceptor/ json/ properties/ utils/
│   │       ├── user/                          # 用户域（controller/service/mapper/model）
│   │       ├── travel/                        # 行程域（Trip/Plan/Itinerary/Guide CRUD）
│   │       └── ai/                            # AI 对接层
│   │           ├── controller/AiController.java   # save-draft / save-trip
│   │           ├── service/AiService.java         # 索引异步管理 + 行程保存
│   │           ├── client/VagoAiClient.java       # HTTP 客户端（含 Spring Retry）
│   │           ├── config/AiClientConfig.java     # @EnableAsync + @EnableRetry
│   │           └── model/                         # AiPlanSaveDTO / AiPlanSaveVO
│   │
│   └── vago-ai/                # ✅ Python FastAPI AI 服务（:8000）
│       ├── main.py             # FastAPI 入口 + CORS + 限流中间件
│       ├── requirements.txt
│       ├── app/
│       │   ├── config.py       # Pydantic Settings（多 Provider 兼容）
│       │   ├── models/schemas.py   # 所有 Pydantic Schema
│       │   ├── dependencies/
│       │   │   ├── auth.py         # JWT 验证（asyncio Redis 连接池）
│       │   │   └── rate_limit.py   # IP + 用户级别限流
│       │   ├── routers/
│       │   │   ├── chat.py         # SSE 流式 + 非流式对话
│       │   │   ├── articles.py     # 攻略入库/检索/删除
│       │   │   └── ai.py          # 预留端点
│       │   └── services/
│       │       ├── rag_chain.py    # LangChain Tool-Calling Agent
│       │       ├── plan_extractor.py  # 结构化行程提取（两步法）
│       │       ├── llm.py         # LLM 工厂（多 Provider）
│       │       ├── vector_store.py # Qdrant CRUD（按 user_uuid 隔离）
│       │       ├── embedder.py    # OpenAI Embedding
│       │       ├── indexer.py     # 攻略入库编排
│       │       ├── chunker.py     # 语义分块
│       │       ├── cleaner.py     # HTML/文本清洗
│       │       └── metadata_extractor.py
│   │
│   └── nginx/
│       └── nginx.conf            # 生产 Nginx 反向代理
│
├── data/
│   └── collections/vago_articles/  # Qdrant 向量数据（磁盘存储）
│
├── docs/
│   ├── prd/PRD.md
│   ├── database/schema.md
│   ├── API/                     # API 文档
│   ├── USAGE.md                 # 本地开发指南
│   └── architecture.md          # 本文件
│
├── dev-up.sh                    # 一键启动脚本
├── .env.example
└── README.md
```

---

## 请求链路（本地开发）

```
浏览器 localhost:5173
    │
    ├── /api/v1/user/**         →  Vite proxy  →  Java vago-backend :8080
    ├── /api/v1/travel/**       →  Vite proxy  →  Java vago-backend :8080
    ├── /api/v1/ai/plans/**     →  Vite proxy  →  Java vago-backend :8080
    │                                                            │
    │                               JWT 拦截器 → Controller → Service → Mapper
    │                                                            ├── MySQL :3306
    │                                                            └── Redis :6379
    │
    └── /api/v1/ai/chat/**     →  Vite proxy  →  Python vago-ai :8000（直连，消除 SSE 代理）
                                                                 │
                              JWT 验证（Python auth.py）→ Router → RAG Agent
                                                                 ├── Qdrant :6333（向量检索）
                                                                 ├── Redis :6379（JWT 黑名单 + 限流）
                                                                 └── OpenAI API（LLM + Embedding）
```

### 生产环境（Nginx）

```
浏览器 :80
    │
    ├── /api/v1/ai/chat/**     →  Nginx → Python :8000（proxy_buffering off）
    ├── /api/v1/**              →  Nginx → Java :8080
    └── /                       →  Nginx → 静态文件 (/var/www/vago-web/dist/)
```

---

## 包结构设计原则

```
com.vago
├── # 基础设施包（跨域）：所有业务域共享，不依赖任何域
│   common / config / constant / context / handler / interceptor / json / properties / utils
│
└── # 业务域包（按域隔离）：域内自治，不跨域直接依赖
    user / travel / ai
```

新增业务域时：
1. 在 `com.vago.<domain>/` 下建 `controller / service / mapper / model` 四层
2. 在 `WebMvcConfiguration.addInterceptors()` 追加需要保护的路径
3. `@MapperScan("com.vago.**.mapper")` 自动扫描，无需修改主类

---

## 技术选型

### Java 后端
| 技术 | 版本 | 用途 |
|------|------|------|
| Spring Boot | 3.2.5 | 单体框架 |
| MyBatis | 3.0.3 (starter) | ORM |
| WebClient (WebFlux) | 3.2.5 | 调用 Python AI 服务 |
| Spring Retry | 3.2.5 | Java → Python 重试容错 |
| MySQL | 8.0 | 主数据库 |
| Redis | 6.x+ | Token 黑名单、限流、验证码 |
| JJWT | 0.12.5 | JWT 签发/校验 |
| SpringDoc OpenAPI | 2.3.0 | Swagger UI |

### Python AI 服务
| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.111 | Web 框架 |
| LangChain | 0.2.5 | LLM Agent 编排 |
| OpenAI SDK | 1.35.3 | GPT 调用 + Embedding |
| Qdrant Client | 1.9.1 | 向量数据库客户端 |
| Redis (asyncio) | 5.0.7 | 限流 + JWT 黑名单 |
| Uvicorn | 0.30 | ASGI 服务器 |

### 前端
| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| Vite | 5.3 | 构建 + 代理 |
| Tailwind CSS | 3.4 | 样式 |
| Axios | 1.7 | HTTP 客户端 |

---

## 本地端口分配

| 进程 | 端口 | 说明 |
|------|------|------|
| MySQL | 3306 | 宿主机直接运行 |
| Redis | 6379 | 宿主机直接运行 |
| vago-backend | **8080** | Java Spring Boot 单体 |
| vago-ai | **8000** | Python FastAPI（uvicorn） |
| vago-web | **5173** | Vite Dev Server |
| Qdrant | **6333** | 向量数据库 |

---

## 关键数据流

### 攻略向量化流程
```
用户创建/更新攻略
    │
    ▼
GuideController → GuideService → MySQL 持久化
    │                              ▲
    ▼                              │
AiServiceImpl.indexGuideAsync()    │
    │  (@Async)                    │
    ▼                              │
VagoAiClient.ingestGuide()        │
    │  (Spring Retry 最多 3 次)     │
    ▼                              │
Python POST /api/v1/articles/ingest│
    │                              │
    ├─ cleaner → chunker          │
    ├─ embedder → Qdrant upsert   │
    └─ 返回 IngestResponse ────────┘
                                   
└→ guideMapper.updateAiStatus(INDEXED/FAILED)
```

### AI 对话流程
```
用户发送消息
    │
    ▼
前端 POST /api/v1/ai/chat/stream（直连 Python）
    │
    ▼
Python auth.py（JWT 验证 + Redis 黑名单检查）
    │
    ▼
rate_limit（IP + 用户级别限流）
    │
    ▼
rag_chain.py（LangChain Tool-Calling Agent）
    ├─ 搜索用户私有攻略库（Qdrant RAG）
    ├─ 调用 LLM 生成回答
    ├─ SSE 流式输出 token
    └─ 文本回答 → plan_extractor 提取结构化行程
    │
    ▼
前端渲染：打字机效果 → 来源引用 → 结构化计划保存按钮
```

---

## 待办事项

- [ ] 实现移动端 App（React Native / Flutter）
- [ ] 足迹地图模块（GPS 轨迹、迷雾解锁）
- [ ] 限流策略支持可配置化（管理后台）
- [ ] AI 回答流中断重连机制
- [ ] 清理废弃的 `vago-gateway` 和 `vago-service-user` 目录
