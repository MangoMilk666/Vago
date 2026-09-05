# Changelog

本文件根据 Git 提交历史整理，版本号采用项目当前的预发布语义化版本约定。每个版本均对应一段已提交的、可追溯的功能演进；尚未发布的工作应先写入 `Unreleased`，发布时再归入下一个版本。

## [Unreleased]

当前没有尚未归档到版本号的已提交变更。

## [v0.8.0] - 2026-09-05

### Added

- 新增 SwiftUI iOS 客户端基础工程、手机号登录、Keychain 会话存储、令牌自动刷新和当前行程查看。
- 新增 Travel Footprint 后端领域：GPS 批量同步、按 `user_uuid + client_uuid` 幂等去重、轨迹读取和手动打卡 API。
- 新增 iOS 前台 Core Location 采样、本地 `UserDefaults` 待传队列、网络恢复后的批量同步，以及全屏 MapKit 记录页。
- 新增按采样时间排序的轨迹分段、15 米渲染降采样、异常跳点断开和 Catmull-Rom 展示平滑。

### Changed

- iOS 地图支持当前定位、自动镜头聚焦、服务端轨迹线与打卡标记的联合渲染。
- 手动打卡改为点击后请求一次新坐标并冻结提交位置；客户端与服务端统一使用 30 米最小重复距离。
- 补充 iOS Travel Map 分阶段实施计划、真机验证要求和全量数据库 DDL。

### Fixed

- 修复 iOS 登录键盘无法收起、Simulator 日期格式兼容、页面尺寸适配和启动安装配置问题。
- 修复 Travel Map 标签页重复切换造成的重复请求和服务端限流问题。

## [v0.7.0] - 2026-09-04

### Added

- 完成正式 Trip 的 `未开始 / 进行中 / 已结束` 生命周期、开始/结束入口和历史行程只读约束。
- 增加计划与正式行程的界面区分，并完成同一日期日程记录的去重约束。

### Fixed

- RAG 未启用或 Qdrant 不可用时，前端保留资料卡片状态并展示会自动消失的顶部错误 Banner。

### Changed

- Web 首页回归简洁的多入口卡片布局，同时保留优化后的固定顶部导航。

## [v0.6.0] - 2026-09-02

### Added

- 新增独立 `knowledge_sources` 模型、纯文本与 UTF-8 `.md` / `.txt` 文件导入、本地存储抽象和索引状态管理。
- 新增用户隔离的 KnowledgeSource CRUD、可选语义索引与相关业务测试。

### Changed

- 将个人资料能力从社区 `Guide` 语义中分离；Personal Context Retrieval 可按需要选择 Direct Context、SQL 或 RAG。
- Web 管理入口统一为“个人知识库”，不再作为旧社区攻略管理面板展示。

### Fixed

- 索引请求在 RAG 关闭或向量服务不可用时提前失败，不再返回误导性的成功响应。

## [v0.5.0] - 2026-09-01

### Added

- 完成 FastAPI Trip、Plan、Itinerary 核心 CRUD，以及 AI 结构化计划保存链路迁移。
- 引入 Alembic 增量迁移，覆盖知识源、行程状态和日程唯一性相关数据库演进。

### Changed

- Vite 将旅行核心、知识库、认证和 AI 对话请求逐步代理到 FastAPI；未迁移 API 继续兼容 Spring Boot。

## [v0.4.0] - 2026-08-30

### Added

- 完成 FastAPI 手机号认证、用户资料、JWT 校验和旧 `/api/v1/user` 兼容路径。
- 新增认证兼容测试与配置 fallback 覆盖。

### Changed

- MySQL 连接配置拆分为独立字段，便于不同开发与部署环境配置。

## [v0.3.0] - 2026-08-28

### Added

- 建立 FastAPI Modular Monolith 的基础配置、数据库、异常、响应与依赖注入骨架。
- 新增 remould 盘点、产品需求和迁移方向文档。

### Changed

- 项目从以旅行社区为主的混合系统，转向 Personal Travel Intelligence、AI 规划与旅行足迹的渐进式重塑。

## [v0.2.0] - 2026-06-22

### Added

- 增加攻略收藏夹、Web 收藏夹面板与防重复收藏逻辑。

### Changed

- 优化攻略点赞统计的异步回写与 Bloom Filter 路径。

## [v0.1.0] - 2026-06-07

### Added

- 发布旅行社区 MVP：React Web、Spring Boot 服务、攻略、点赞、收藏和 AI 对话基础能力。
- 增加 GitHub OAuth 登录、SSE AI 对话流处理、核心 CRUD API 代理和 Redis 连接池。

### Changed

- AI 对话 SSE 从 Java 代理调整为由 Python 服务直接处理。

[Unreleased]: https://github.com/MangoMilk666/Vago/compare/v0.8.0...HEAD
[v0.8.0]: https://github.com/MangoMilk666/Vago/compare/v0.7.0...v0.8.0
[v0.7.0]: https://github.com/MangoMilk666/Vago/compare/v0.6.0...v0.7.0
[v0.6.0]: https://github.com/MangoMilk666/Vago/compare/v0.5.0...v0.6.0
[v0.5.0]: https://github.com/MangoMilk666/Vago/compare/v0.4.0...v0.5.0
[v0.4.0]: https://github.com/MangoMilk666/Vago/compare/v0.3.0...v0.3.0
[v0.3.0]: https://github.com/MangoMilk666/Vago/compare/v0.2.0...v0.3.0
[v0.2.0]: https://github.com/MangoMilk666/Vago/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/MangoMilk666/Vago/releases/tag/v0.1.0
