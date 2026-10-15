# Travel Footprint API

**状态：当前 FastAPI 接口摘要。** 路由与 schema 分别在 `services/vago-ai/app/footprints/router.py` 和 `schemas.py`。所有路径以 `/api/v1/footprints` 开头，必须携带 Bearer token；服务端校验 Trip 属于已认证用户。成功响应使用 `{ code, message, data }`。

`TravelObservation` 统一表示空间观察，用 `observationType` 区分 `AUTO_GPS` 与 `MANUAL_CHECKIN`。同一可信连续段内，打卡可以是轨迹顶点，同时保留独立打卡标记；段边界与异常定位不得被打卡跨越。原始观察坐标不因显示层平滑而改变。

## 自动 GPS

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/location-samples/sync` | 将一个 Trip 的 1–100 条待传 GPS 样本幂等同步 |
| GET | `/trips/{tripUuid}/locations` | 兼容旧客户端的仅 GPS 列表 |

同步请求含 `tripUuid` 与 `samples`。每条样本有稳定的 `clientUuid`、`latitude`、`longitude`、`recordedAt`，可选 `accuracyM`、`speedMps`、`trackingSegmentUuid`。响应分别返回 `acceptedCount`、`duplicateCount`、`skippedCount`；客户端应以成功响应为依据移除对应待传项。已结束 Trip 可补传先前离线记录的 GPS，不能新建手动打卡。

## 统一观察与打卡

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/trips/{tripUuid}/observations` | 读取 GPS 与手动打卡的统一观察流 |
| GET | `/trips/{tripUuid}/checkins` | 兼容旧客户端的仅打卡列表 |
| POST | `/observations/checkins` | 创建打卡并返回统一观察对象 |
| PATCH | `/observations/checkins/{observationUuid}` | 只修改用户输入的地点名和备注 |
| POST | `/checkins` | 兼容旧客户端的打卡创建入口 |

打卡创建请求含 `tripUuid`、`locationName`、`latitude`、`longitude`，可选 `note`、`checkedAt`、`trackingSegmentUuid` 与 `clientEventUuid`。新客户端应提供稳定的 `clientEventUuid` 以防重试重复创建。手动打卡只允许写入进行中的 Trip；更新入口不能修改坐标、时间、类型或段标识。统一观察响应包括 `uuid`、`clientEventUuid`、`tripUuid`、`observationType`、坐标、可选的精度/速度/段标识/文本，以及 `occurredAt`。

地图分段、过滤和可见点密度属于显示层，详见 [足迹设计](../modules/footprint/ios/design.md)。
