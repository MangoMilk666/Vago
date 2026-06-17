# Vago（叠迹）

> 一站式旅行管理平台——攻略整合 × AI 智能规划 × 行程管理

---

## 项目简介

**Vago**（叠迹）是一个面向自由行旅客的一站式旅行管理平台，将旅行的「前、中、后」三个阶段完整打通。

市面上的旅行类产品高度碎片化：攻略散落在小红书、公众号；行程规划依赖固定模板；足迹记录与攻略脱节。Vago 的核心思路是：**以用户私有攻略库为资产核心，让攻略真正服务于规划，让规划真正映射到足迹。**

项目采用 **Java Spring Boot + Python FastAPI 混合单体架构**，Java 侧负责用户系统与行程 CRUD，Python 侧负责 RAG 检索与 LLM 智能规划，前端使用 React 构建 SPA。

---

## 核心功能

### RAG 智能攻略库

将用户从各渠道收集的零散攻略（粘贴文本、URL 导入）结构化入库，经过 HTML 清洗、语义分块（tiktoken + RecursiveCharacterTextSplitter）、OpenAI Embedding 向量化后，存入 Qdrant 向量数据库，形成按 `user_uuid` 隔离的个人知识库。

### AI 行程伴侣

用户以自然语言描述需求（目的地、天数、预算、偏好），AI 基于 LangChain Tool-Calling Agent **自主决策**是否检索用户攻略库（RAG），生成定制化行程草稿。支持 SSE 全链路流式输出、多轮追问与局部修改，最终一键提取结构化行程数据并保存。

### 行程与目的地管理

支持创建多目的地旅行计划，按天编排景点、餐饮、交通等信息。提供仪表盘总览、行程看板编辑等管理能力。

### 用户系统

手机号 + 短信验证码登录/注册，JWT 无状态鉴权，Redis Token 黑名单，个人设置管理。

---

## 技术栈

| 层次 | 技术 | 版本 |
|------|------|------|
| **前端** | React + Vite + Tailwind CSS | 18.3 / 5.3 / 3.4 |
| **路由** | React Router | 6.24 |
| **HTTP** | Axios | 1.7 |
| **后端** | Spring Boot（单体） | 3.2.5 |
| **ORM** | MyBatis | 3.0.3 |
| **鉴权** | JJWT | 0.12.5 |
| **API 文档** | SpringDoc OpenAPI | 2.3.0 |
| **工具库** | Hutool | 5.8.26 |
| **AI 框架** | FastAPI + LangChain | 0.111 / 0.2.5 |
| **LLM** | OpenAI SDK | 1.35.3 |
| **向量数据库** | Qdrant | 1.9.1 |
| **Embedding** | tiktoken + OpenAI | ≥0.7 |
| **主数据库** | MySQL | 8.0+ |
| **缓存** | Redis | 6.0+ |

---

## 系统架构

```
┌──────────────────────────────────────────────┐
│           浏览器 (React SPA)                  │
│           localhost:5173                      │
└──┬──────────────────────────┬────────────────┘
   │ /api/v1/ai/chat/**       │ /api/v1/** (其它 API)
   │（直连 Python）            │
   ▼                          ▼
┌─────────────────┐    ┌──────────────────────────┐
│ vago-ai (Python)│    │ vago-backend (Spring Boot)│
│ FastAPI :8000   │    │ :8080                     │
│                 │    │                           │
│ · RAG 攻略检索  │    │ · 用户认证 / JWT          │
│ · SSE 对话流    │    │ · 攻略/行程 CRUD           │
│ · 结构化提取    │    │ · AI 结果保存（save-*）    │
│                 │    │                           │
│ Qdrant :6333    │    │ MySQL :3306 / Redis :6379 │
└─────────────────┘    └──────────────────────────┘
```

**架构说明**：项目最初采用微服务架构（Gateway + User Service），后根据业务规模演进为混合单体。**关键设计决策**：AI 对话接口（chat / chat/stream）由前端通过 Vite 代理直接路由至 Python vago-ai，消除 Java SSE 代理链路，降低延迟。Java 后端负责所有 CRUD 与鉴权，以及攻略向量化（异步 HTTP 调用 Python）和 AI 行程保存业务逻辑。Python 端独立验证 JWT（共享 HS256 secret + Redis 黑名单），并实现 IP/用户级别请求限流。

---

## 目录结构

```
Vago/
├── apps/
│   └── vago-web/                          # React 18 + Vite 5 前端
│       ├── src/
│       │   ├── api/                       # Axios 请求封装（user.js, travel.js, ai.js）
│       │   ├── pages/                     # 页面组件
│       │   │   ├── LoginPage.jsx          #   手机号登录/注册
│       │   │   ├── DashboardPage.jsx      #   仪表盘
│       │   │   ├── TripPage.jsx           #   旅行计划管理
│       │   │   ├── ItineraryPage.jsx      #   行程详情编辑
│       │   │   ├── AiPlanPage.jsx         #   AI 对话式行程规划
│       │   │   ├── GuidePage.jsx          #   攻略库管理
│       │   │   ├── PlanPage.jsx           #   行程总览
│       │   │   └── ProfilePage.jsx        #   个人设置
│       │   ├── stores/                    # 状态管理
│       │   └── App.jsx                    # React Router 路由配置
│       └── vite.config.js                 # Vite 代理 + 构建配置
│
├── services/
│   ├── pom.xml                            # Maven 父 POM
│   │
│   ├── vago-backend/                      # Java Spring Boot 单体后端
│   │   └── src/main/java/com/vago/
│   │       ├── VagoApplication.java       #   启动入口
│   │       ├── common/                    #   统一响应、错误码
│   │       ├── config/                    #   WebMvc、Swagger、Redis 配置
│   │       ├── constant/                  #   JWT Claims 常量
│   │       ├── context/                   #   ThreadLocal 上下文
│   │       ├── exception/                 #   自定义异常
│   │       ├── handler/                   #   全局异常处理
│   │       ├── interceptor/               #   JWT 鉴权拦截器
│   │       ├── json/                      #   Jackson 序列化配置
│   │       ├── properties/                #   配置属性类
│   │       ├── utils/                     #   JWT、Hutool 工具类
│   │       ├── user/                      #   用户域（controller/service/mapper/model）
│   │       ├── travel/                    #   行程域（trip/itinerary CRUD）
│   │       └── ai/                        #   AI 对接层（DTO/WebClient 桥接）
│   │
│   └── vago-ai/                           # Python FastAPI AI 服务
│       ├── main.py                        #   FastAPI 入口 + CORS
│       ├── requirements.txt
│       └── app/
│           ├── config.py                  #   应用配置（Settings）
│           ├── routers/                   #   API 路由
│           │   ├── chat.py                #     对话（流式 SSE / 非流式）
│           │   ├── articles.py            #     攻略入库 / 检索 / 删除
│           │   └── ai.py                  #     AI 辅助接口
│           ├── models/                    #   Pydantic 数据模型
│           │   └── schemas.py             #     请求/响应 Schema
│           └── services/                  #   业务逻辑
│               ├── rag_chain.py           #     RAG Agent（Tool-Calling）
│               ├── plan_extractor.py      #     结构化行程提取
│               ├── llm.py                 #     LLM 客户端工厂
│               ├── indexer.py             #     攻略入库编排
│               ├── chunker.py             #     语义分块
│               ├── cleaner.py             #     文本/HTML 清洗
│               ├── metadata_extractor.py  #     元数据提取
│               ├── embedder.py            #     OpenAI Embedding
│               └── vector_store.py        #     Qdrant 向量操作
│
├── docs/
│   ├── prd/PRD.md                         # 产品需求文档
│   ├── database/                          # 数据库设计
│   ├── API/                               # 接口文档
│   ├── USAGE.md                           # 本地开发指南
│   └── architecture.md                    # 架构说明
│
├── dev-up.sh                              # 一键启动脚本
├── .env.example                           # 环境变量模板
└── LICENSE
```

---

## SSE 流式通信协议

AI 对话接口 `POST /api/v1/ai/chat/stream`（前端直连 Python vago-ai）使用 Server-Sent Events 实现流式传输，前端通过 `fetch` + `ReadableStream` 消费。事件类型定义如下：

| 事件类型 | 说明 |
|---------|------|
| `searching` | AI 正在检索用户攻略库 |
| `sources` | 返回检索命中的攻略来源 |
| `text` | LLM 逐 token 输出文本 |
| `extracting_plan` | 开始从回答中提取结构化行程 |
| `structured_plan` | 返回结构化行程数据（JSON） |
| `error` | 服务端错误信息 |
| `[DONE]` | 流结束标记 |

---

## 文档

- [产品需求文档 (PRD)](docs/prd/PRD.md)
- [本地开发指南](docs/USAGE.md)
- [项目架构说明](docs/architecture.md)

---

## License

[Apache License 2.0](LICENSE)
