<h1 align="center">Vago（叠迹）</h1>

[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/github/license/MangoMilk666/Vago?style=flat-square)](LICENSE)

> AI-Native Personal Travel Companion — 一个以个人旅行知识、AI 规划、真实足迹与旅行回忆为核心的个性化旅行搭子。

## 项目简介

**Vago（叠迹）** 是一个面向旅行者用户的 AI-Native 个性化旅行项目。它将攻略、笔记、历史行程、照片和足迹中的旅行信息沉淀为个人旅行知识，并通过 AI 辅助旅行前规划、旅行中记录和旅行后回忆生成。

```text
Personal Travel Knowledge
        ↓
Adaptive Personal Context Retrieval
        ↓
AI Travel Companion
        ↓
Structured Travel Plan
        ↓
User Confirmation
        ↓
Actual Trip
        ↓
GPS / Photos / Notes
        ↓
Travel Footprint
        ↓
AI-generated Travel Memory
        ↓
Personal Travel Profile / Memory
        ↓
Future Personalized Planning
```

## 核心定位

本项目围绕 **Personal Travel Intelligence** 展开：

- 整理用户自己的旅行攻略、笔记和资料；
- 根据用户意图选择合适的个人上下文来源；
- 用 AI 生成可确认、可编辑、可落库的结构化行程；
- 在实际旅行中记录 GPS、照片、笔记和打卡；
- 基于真实旅行数据生成可回顾、可分享、可复用的旅行回忆；
- 将历史旅行逐步沉淀为未来规划可用的个人偏好和记忆。

## 功能模块

| 模块                        | 状态   | 说明                                                               |
| ------------------------- | ---- | ---------------------------------------------------------------- |
| 用户与认证                     | 已实现  | 手机号 / OAuth、JWT、用户级数据隔离、个人设置                                     |
| Personal Travel Knowledge | 已实现  | 独立 KnowledgeSource、纯文本与 `.md/.txt` 导入、用户隔离、Web 知识库与可选语义索引        |
| AI Travel Companion       | 开发中  | 多轮对话、SSE、Tool Calling、结构化计划输出、用户确认后保存                            |
| Plans / Trips / Itinerary | 已实现  | 草稿计划、正式行程、每日安排、景点、交通、住宿、预算                                       |
| Footprints                | 已实现  | iOS 前台 GPS 采样、本地缓冲、幂等同步、MapKit 全屏轨迹线、当前位置镜头与手动打卡                 |
| Fog-of-World Map          | 后续建设 | 基于真实移动轨迹解锁地图区域                                                   |
| Photos / Notes            | 后续建设 | 拍照、相册选择、EXIF / 时间 / 位置绑定、Trip / Spot 关联                          |
| Travel Memory             | 后续建设 | 基于事实数据生成可编辑旅行总结、timeline、highlights、分享卡片                         |
| Native iOS                | 开发中  | SwiftUI 登录、Keychain 会话、当前行程、前台定位、离线同步、MapKit 轨迹分段/平滑渲染、当前定位与手动打卡 |

## 技术栈

| 层次            | 当前使用                                                     | 计划使用               |
| ------------- | -------------------------------------------------------- | ------------------ |
| Web           | React 18、Vite 5、Tailwind CSS                             | 持续完善旅行规划与知识管理体验    |
| iOS           | Swift 6、SwiftUI、MapKit、Core Location、URLSession、Keychain | 扩展足迹、照片、笔记与旅行回忆能力  |
| Backend       | FastAPI 0.111、Pydantic v2、SQLAlchemy 2.x、Alembic         | 保持模块化单体架构，逐步完善领域模块 |
| Relational DB | MySQL                                                    | 保持为结构化旅行数据主存储      |
| Cache         | Redis                                                    | 认证会话、限流与缓存能力       |
| Vector DB     | Qdrant                                                   | 作为个人资料的可选语义检索能力    |
| AI            | LangChain、OpenAI SDK、SSE                                 | 扩展上下文编排与结构化旅行助手能力  |

## 目录结构

```text
Vago/
├── apps/
│   ├── vago-web/                 # React Web
│   └── vago-ios/                 # SwiftUI iOS：旅行中查看、采集与打卡
├── services/
│   ├── vago-ai/                  # FastAPI 后端、领域服务与 Alembic 迁移
│   └── nginx/
├── docs/
│   ├── API/                      # API contract 文档
│   ├── database/                 # 数据库 DDL 与说明
│   └── design/                   # 设计与实施文档
├── dev-up.sh
├── .env.example
└── LICENSE
```

## 双端当前能力

| 能力域    | React Web                         | SwiftUI iOS                                       |
| ------ | --------------------------------- | ------------------------------------------------- |
| 登录与会话  | 手机号 / OAuth、浏览器会话                 | 手机号登录、Keychain 凭证、设备级 refresh session             |
| 知识与 AI | KnowledgeSource 管理、资料导入、AI 规划与对话  | 暂不复制复杂资料管理与规划流程                                   |
| 计划与行程  | Plan / Trip / Itinerary CRUD、日程编辑 | 查看进行中行程与每日安排                                      |
| 旅行足迹   | 仅保留导航占位页，尚未查询或渲染真实足迹数据            | 前台定位采样、本地待传队列、批量幂等同步、服务端轨迹读取、按时间分段的平滑路线、当前定位与手动打卡 |

- iOS 的轨迹数据由 FastAPI 作为长期事实来源：设备先缓存位置样本，成功同步后才从本地队列移除。

- 地图会按采样时间排序，以 15 米渲染阈值降采样，并在长时间间隔或异常远跳处断开，避免把不连续移动伪造成路线；随后用展示层插值绘制更自然的轨迹线。

- 打卡已可写入服务端并渲染为地图标记；创建时会请求一条新坐标，客户端与服务端共同拒绝同一行程 30 米内的重复打卡。

## 数据库初始化

全量 DDL 位于 [db_schema.sql](docs/database/db_schema.sql)，用于**全新本地数据库**。脚本会 `DROP TABLE` 后重建当前所需表。

```bash
mysql -u <user> -p <database_name> < docs/database/db_schema.sql
```

已有数据库应谨慎运行全量 DDL；可在 `services/vago-ai` 下执行 Alembic 增量迁移：

```bash
.venv/bin/alembic upgrade head
```

## 文档

- [项目需求文档](docs/prd/PRD.md)
- [项目架构说明](docs/architecture.md)
- [版本更新记录](docs/CHANGELOG.md)
- [数据库文档](docs/database/schema.md)
- [用户服务 API](docs/API/user-service.md)
- [旅行核心 API](docs/API/travel-service.md)
- [个人知识 API](docs/API/knowledge-service.md)
- [旅行足迹 API](docs/API/footprint-service.md)

## License

[Apache License 2.0](LICENSE)
