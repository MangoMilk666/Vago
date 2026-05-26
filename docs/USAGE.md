# 本地联调开发指南

> 架构：Java 单体后端（:8080）+ Python AI 服务（:8000）+ React 前端（:5173）

---

## 目录

- [环境要求](#环境要求)
- [本地服务架构](#本地服务架构)
- [快速启动（一键脚本）](#快速启动一键脚本)
- [手动逐服务启动](#手动逐服务启动)
- [接口测试](#接口测试)
- [常见问题](#常见问题)

---

## 环境要求

| 工具 | 版本要求 | 安装方式 |
|------|----------|---------|
| Java | 17+ | `brew install openjdk@17` |
| Maven | 3.8+ | `brew install maven` |
| Python | 3.11+ | `brew install python@3.11` |
| MySQL | 8.0+ | `brew install mysql` |
| Redis | 6.0+ | `brew install redis` |
| Node.js | 18+ | `brew install node` |
| nc (netcat) | 系统自带 | macOS 内置 |

---

## 本地服务架构

```
浏览器 (localhost:5173)
    │
    ├── /api/v1/user/**  →  Vite 代理  →  vago-backend  :8080
    │                                          │
    │                                    Spring Boot 单体
    │                                    （用户 / 行程 / 足迹 CRUD）
    │                                          ├── MySQL  :3306
    │                                          └── Redis  :6379
    │
    └── /api/v1/ai/**   →  Vite 代理  →  vago-ai  :8000
                                              │
                                        Python FastAPI
                                        （行程规划 / RAG 检索）
```

---

## 快速启动（一键脚本）

### 1. 初始化数据库

```bash
# 启动 MySQL 和 Redis
brew services start mysql
brew services start redis

# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS vago CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 执行建表 SQL（参见 docs/database/schema.md）
# mysql -u root -p vago < docs/database/schema.sql
```

### 2. 配置数据库密码

编辑 `services/vago-backend/src/main/resources/application-dev.yml`：

```yaml
spring:
  datasource:
    password: "你的MySQL密码"   # ← 改这里
```

### 3. 一键启动

```bash
# 赋予执行权限（首次）
chmod +x dev-up.sh

# 启动全部服务（Java 后端 + Python AI + 前端）
./dev-up.sh
```

启动成功后终端显示：

```
════════════════════════════════════════════
[OK]    所有服务已就绪！
  Java 后端  →  http://localhost:8080/swagger-ui.html
  AI  服务   →  http://localhost:8000/docs
  Web 前端   →  http://localhost:5173
════════════════════════════════════════════
```

### 4. 常用启动选项

```bash
# 只启动 Java 后端（不启 AI 和前端）
./dev-up.sh --no-ai --no-web

# 只启动前端（后端已运行）
./dev-up.sh --no-backend --no-ai

# 跳过 AI 服务（功能未用到时）
./dev-up.sh --no-ai
```

按 `Ctrl+C` 停止所有服务。日志保存在 `.log/` 目录：

```
.log/
├── backend.log   # Java 后端日志
├── ai.log        # Python AI 服务日志
└── web.log       # Vite 前端日志
```

---

## 手动逐服务启动

需要更精细控制时，在多个终端分别运行：

### 终端 1：Java 后端

```bash
cd services/vago-backend
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

### 终端 2：Python AI 服务

```bash
cd services/vago-ai

# 首次：创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 启动（--reload 支持热重载）
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 终端 3：前端

```bash
cd apps/vago-web
npm install     # 首次安装依赖
npm run dev
```

---

## 接口测试

### Swagger UI（Java 后端）

```
http://localhost:8080/swagger-ui.html
```

### FastAPI 文档（Python AI 服务）

```
http://localhost:8000/docs
```

### curl 示例

```bash
# 发送短信验证码
curl -X POST http://localhost:8080/api/v1/user/sms/send \
  -H "Content-Type: application/json" \
  -d '{"phone":"+8613800138000","scene":"LOGIN"}'

# 手机号登录
curl -X POST http://localhost:8080/api/v1/user/login/phone \
  -H "Content-Type: application/json" \
  -d '{"phone":"+8613800138000","smsCode":"123456"}'

# 获取当前用户信息（替换 YOUR_TOKEN）
curl http://localhost:8080/api/v1/user/profile \
  -H "authorization: YOUR_ACCESS_TOKEN"

# AI 行程规划
curl -X POST http://localhost:8000/api/v1/ai/plan \
  -H "Content-Type: application/json" \
  -d '{"destination":"日本京都","days":3,"style":"culture"}'

# AI 健康检查
curl http://localhost:8000/health
```

---

## 常见问题

### Q: 启动报 `Address already in use`

```bash
# 查找占用端口的进程
lsof -iTCP:8080 -sTCP:LISTEN -n -P   # Java 后端
lsof -iTCP:8000 -sTCP:LISTEN -n -P   # Python AI

# 杀掉进程
kill -9 <PID>
```

### Q: Python 依赖安装失败

macOS 受 PEP 668 影响，禁止直接向系统 Python 安装包，必须用虚拟环境：

```bash
cd services/vago-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Q: 前端调接口报 CORS 错误

检查 `apps/vago-web/vite.config.js` 代理配置：

```js
proxy: {
  '/api/v1': { target: 'http://localhost:8080' },   // Java 后端
  '/api/v1/ai': { target: 'http://localhost:8000' } // Python AI
}
```

前端所有请求经 Vite 代理转发，**不会产生跨域问题**。

### Q: MySQL 连接失败

检查 `application-dev.yml` 中的用户名和密码是否正确，并确认数据库已创建：

```bash
mysql -u root -p -e "SHOW DATABASES LIKE 'vago';"
```

### Q: Java 后端启动后 Swagger 页面打不开

`WebMvcConfiguration` 继承了 `WebMvcConfigurationSupport`，Spring Boot 的静态资源自动配置会退出，需手动注册。已在代码中配置，若仍打不开请检查 `application.yml` 中的 `springdoc` 配置项是否存在。

---

## 目录速查

```
Vago/
├── dev-up.sh                              # 一键启动脚本
├── .log/                                  # 运行日志（本地，不提交 Git）
├── apps/
│   └── vago-web/                          # React + Vite 前端
├── services/
│   ├── vago-backend/                      # Java Spring Boot 单体
│   │   └── src/main/resources/
│   │       ├── application.yml            # 主配置（不含密码）
│   │       └── application-dev.yml        # 开发环境配置（含密码，勿提交）
│   └── vago-ai/                           # Python FastAPI AI 服务
│       ├── main.py
│       └── requirements.txt
└── docs/
    ├── API/user-service.md                # 用户接口文档
    ├── database/schema.md                 # 数据库设计
    ├── USAGE.md                           # 本文件
    └── architecture.md                    # 架构说明
```
