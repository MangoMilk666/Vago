# Footprint 测试数据工具

## 目标

为 Travel Map、Footprint Domain、Personal Travel Context 与 Agent 提供可重复、可清理的本地开发数据。测试数据只能服务于开发和演示，不能混入真实用户旅行事实。

`AUTO_GPS` 与 `MANUAL_CHECKIN` 继续是同一类 Travel Footprint：前者表示系统自动采样，后者表示用户主动确认的特殊足迹点。

## 命名与迁移

当前事实表为 `travel_observations`。后续统一更名为 `travel_footprints`，使表名与 Footprint Domain、地图和 API 概念一致。

- 该变更使用独立 Alembic migration 完成表重命名、索引与约束校验；不删表重建。
- 已有 GPS、打卡、幂等键和 Trip 归属必须原样保留。
- 测试工具通过 Footprint 的服务/模型边界写入，不依赖表名；迁移前后都可工作。

## Phase 1：CLI 场景 Seed

提供只允许在 `local` / `development` 环境运行的命令行工具。调用时必须显式给出 `--user-uuid`、`--trip-uuid` 与 `--location`，不创建默认账号，不猜测当前行程。

```bash
python -m app.devtools.seed_footprints \
  --user-uuid <user_uuid> \
  --trip-uuid <trip_uuid> \
  --location MARINA_SANDS_BAY \
  --seed 20260924
```

首批固定场景：

| `--location` | 数据内容 | 主要验证点 |
| --- | --- | --- |
| `MARINA_SANDS_BAY` | 滨海湾连续步行轨迹、两段 tracking segment、多个打卡 | polyline、分段、打卡详情、地图缩放 |
| `LONDON` | 模拟在England London的游客区域较长距离的移动、停留点和跨时段打卡 | 时间排序、路线断点、历史 Trip 浏览 |
| `TAHOE` | 模拟在California Lake Tahoe区域较长距离的移动、停留点和跨时段打卡 | 时间排序、路线断点、历史 Trip 浏览 |
| `CHECKIN_PROXIMITY_01` | 临近 GPS 与手动打卡 | 自动采样避让手动打卡、打卡始终可记录 |

每次生成使用固定随机种子与明确时间序列。所有 `client_event_uuid` 使用 `devseed:<run-id>:` 前缀；清理命令只能删除同一 `run-id` 的记录，禁止全表删除。种子数据直接覆盖地图、上下文和 Agent 的读取验证；iOS 离线队列与批量同步仍应由独立集成测试覆盖。

## Phase 2：开发环境地图编辑器

保留 Phase 1 CLI，同时增加仅开发环境可见的 Web 地图模拟器：选择已有测试 Trip 后，可点击地图补充单个自动 GPS 点或手动打卡，并填写时间、名称和备注。

- 使用同一 Footprint Domain Service 写入，不新增生产调试 API。
- 页面必须显著标注“模拟数据”，并受环境开关保护。
- 适合复现边界坐标、近距离打卡和异常路线；完整路线仍优先由 CLI 场景生成。

## 非目标

本工具不上传真实定位、不生成照片、不调用地图或地理编码第三方服务，也不在生产环境提供数据写入入口。
