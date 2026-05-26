# 项目架构

> 最后更新：2026-05-24｜架构：混合单体（Java CRUD + Python AI）

---

## 当前实现状态

| 模块 | 路径 | 状态 | 说明 |
|------|------|------|------|
| vago-backend | `services/vago-backend/` | ✅ 完成 | Java Spring Boot 单体，端口 8080 |
| vago-ai | `services/vago-ai/` | 🟡 骨架 | Python FastAPI AI 服务，端口 8000 |
| vago-web | `apps/vago-web/` | ✅ 完成 | React + Vite 前端，端口 5173 |
| ~~vago-gateway~~ | `services/vago-gateway/` | ⛔ 已废弃 | 单体架构不需要网关，目录保留 |
| ~~vago-service-user~~ | `services/vago-service-user/` | ⛔ 已废弃 | 代码已迁入 vago-backend，目录保留 |

---

## 架构演进历史

```
v0.1（初始微服务）：
  vago-gateway:8080 → vago-service-user:8081

v0.2（当前 · 混合单体）：
  vago-backend:8080  ← 所有 CRUD
  vago-ai:8000       ← AI 功能（Python）
```

---

## 总目录

```
Vago/
├── apps/
│   └── vago-web/               # ✅ React 18 + Vite 5 + Tailwind CSS
│       ├── src/
│       │   ├── api/user.js          # Axios 封装
│       │   ├── pages/LoginPage.jsx  # 三步 SMS 登录/注册
│       │   ├── pages/DashboardPage.jsx
│       │   ├── stores/auth.js       # localStorage 状态管理
│       │   └── App.jsx              # React Router v6
│       └── vite.config.js      # 代理：/api/v1 → :8080，/api/v1/ai → :8000
│
├── services/
│   ├── pom.xml                 # Maven 父 POM（只构建 vago-backend）
│   │
│   ├── vago-backend/           # ✅ Java 单体后端（Spring Boot 3.2.5，:8080）
│   │   └── src/main/java/com/vago/
│   │       ├── VagoApplication.java           # 主类，@MapperScan("com.vago.**.mapper")
│   │       │
│   │       ├── # ── 基础设施层（跨域共享）──────────────────────────────
│   │       ├── common/
│   │       │   ├── Result.java                # 统一响应包装
│   │       │   └── ResultCode.java            # 业务错误码枚举
│   │       ├── config/
│   │       │   ├── WebMvcConfiguration.java   # 拦截器 + CORS + Jackson 转换器
│   │       │   └── SwaggerConfig.java         # OpenAPI 3 文档配置
│   │       ├── constant/
│   │       │   └── JwtClaimsConstant.java     # JWT Claims 键名
│   │       ├── context/
│   │       │   └── BaseContext.java           # ThreadLocal<String>（存用户 UUID）
│   │       ├── handler/
│   │       │   └── GlobalExceptionHandler.java
│   │       ├── interceptor/
│   │       │   └── JwtTokenUserInterceptor.java
│   │       ├── json/
│   │       │   └── JacksonObjectMapper.java   # LocalDateTime 统一格式
│   │       ├── properties/
│   │       │   └── JwtProperties.java         # @ConfigurationProperties
│   │       └── utils/
│   │           └── JwtUtil.java               # JJWT 0.12.x 工具类
│   │       │
│   │       └── # ── 业务域层（按域拆子包，未来扩展不动基础设施）──────
│   │           ├── user/                      # 用户域
│   │           │   ├── controller/UserController.java
│   │           │   ├── service/UserService.java     # 接口（impl 待完成）
│   │           │   ├── mapper/                      # MyBatis 注解 SQL
│   │           │   │   ├── UserMapper.java
│   │           │   │   ├── UserOauthBindingMapper.java
│   │           │   │   └── UserSettingsMapper.java
│   │           │   └── model/
│   │           │       ├── dto/  (8 个请求 DTO)
│   │           │       ├── entity/ (User, UserOauthBinding, UserSettings)
│   │           │       └── vo/   (LoginVO, TokenVO, UserSettingsVO, UserVO)
│   │           │
│   │           ├── travel/     # 🔲 行程 + 攻略域（待开发）
│   │           └── geo/        # 🔲 足迹地图域（待开发）
│   │
│   ├── vago-ai/                # 🟡 Python FastAPI AI 服务（:8000）
│   │   ├── main.py             # FastAPI 入口 + CORS
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── routers/ai.py   # POST /api/v1/ai/plan, /search（含占位实现）
│   │       └── services/       # LangChain / LLM 业务逻辑（待接入）
│   │
│   ├── vago-gateway/           # ⛔ 已废弃（单体无需路由网关）
│   └── vago-service-user/      # ⛔ 已废弃（代码已迁入 vago-backend）
│
├── docs/
│   ├── prd/PRD.md
│   ├── database/schema.md
│   ├── API/user-service.md
│   ├── USAGE.md
│   └── architecture.md        # 本文件
│
├── dev-up.sh                   # ✅ 一键启动（Java + Python + Vite）
├── .env.example
└── README.md
```

---

## 本地端口分配

| 进程 | 端口 | 说明 |
|------|------|------|
| MySQL | 3306 | 宿主机直接运行 |
| Redis | 6379 | 宿主机直接运行 |
| vago-backend | **8080** | Java Spring Boot 单体 |
| vago-ai | **8000** | Python FastAPI（uvicorn） |
| vago-web | **5173** | Vite Dev Server |

---

## 请求链路（本地开发）

```
浏览器 localhost:5173
    │
    ├── /api/v1/user/**  →  Vite proxy  →  Java vago-backend :8080
    │                           │
    │                           ├── JWT 拦截器（JwtTokenUserInterceptor）
    │                           ├── Controller → Service → Mapper
    │                           ├── MySQL :3306
    │                           └── Redis :6379
    │
    └── /api/v1/ai/**   →  Vite proxy  →  Python vago-ai :8000
                                │
                                ├── FastAPI Router
                                └── LangChain + LLM（待接入）
```

---

## 包结构设计原则

```
com.vago
├── # 基础设施包（跨域）：所有业务域共享，不依赖任何域
│   common / config / constant / context / handler / interceptor / json / properties / utils
│
└── # 业务域包（按域隔离）：域内自治，不跨域直接依赖
    user / travel / geo / ai-client（未来）
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
| MySQL | 8.0 | 主数据库 |
| Redis | 6.x+ | Token 黑名单、验证码缓存 |
| JJWT | 0.12.5 | JWT 签发/校验 |
| SpringDoc OpenAPI | 2.3.0 | Swagger UI |

### Python AI 服务
| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.111 | Web 框架 |
| LangChain | 0.2.x | LLM 编排 |
| OpenAI SDK | 1.35 | GPT 调用 |
| Uvicorn | 0.30 | ASGI 服务器 |

### 前端
| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| React Router | 6.x | 路由 |
| Vite | 5.x | 构建 + 代理 |
| Tailwind CSS | 3.x | 样式 |
| Axios | 1.x | HTTP 客户端 |

---

## 待办事项

- [ ] 实现 `UserServiceImpl`（完整业务逻辑 + Redis 验证码）
- [ ] 编写数据库初始化 SQL（`docs/database/schema.sql`）
- [ ] 接入 LangChain + OpenAI 实现 AI 行程规划
- [ ] 接入向量数据库（Milvus/Qdrant）实现攻略 RAG 检索
- [ ] 开发 travel 域（行程 + 攻略 CRUD）
- [ ] 开发 geo 域（足迹地图 + 打卡统计）
- [ ] 清理废弃的 `vago-gateway` 和 `vago-service-user` 目录
