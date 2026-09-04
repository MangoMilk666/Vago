# Travel Footprint API

Phase 8 新增的足迹接口由 FastAPI `/api/v1/footprints` 提供。它们只服务登录用户自己的正式行程，不依赖 Web Cookie，也不暴露任何社区或公开地图数据。

## 认证与边界

所有接口都需要请求头：

```text
Authorization: Bearer <access-token>
```

- GPS 样本必须绑定当前用户拥有的未删除 Trip。
- 位置批量同步按 `userUuid + clientUuid` 幂等，可安全重试。
- 手动打卡仅允许写入 `进行中(status=2)` 的行程。
- 已结束行程可接收此前离线缓存的 GPS 样本，但不能新增手动打卡，避免旅行历史被继续编辑。

## 同步 GPS 样本

`POST /api/v1/footprints/location-samples/sync`

一次最多传入 100 条记录。iOS 应先写入本地队列，收到成功响应后才删除该批样本。

```json
{
  "tripUuid": "trip-uuid",
  "samples": [{
    "clientUuid": "ios-local-uuid",
    "latitude": 1.3521,
    "longitude": 103.8198,
    "accuracyM": 12.5,
    "speedMps": 1.4,
    "recordedAt": "2026-09-04T09:00:00Z"
  }]
}
```

```json
{
  "code": 200,
  "message": "轨迹同步成功",
  "data": { "acceptedCount": 1, "duplicateCount": 0 }
}
```

## 读取行程轨迹

`GET /api/v1/footprints/trips/{tripUuid}/locations`

按采样时间升序返回当前用户该行程的已同步轨迹点，供 MapKit 或 Web 地图回放使用。

## 手动打卡

`POST /api/v1/footprints/checkins`

```json
{
  "tripUuid": "trip-uuid",
  "locationName": "滨海湾花园",
  "latitude": 1.2816,
  "longitude": 103.8636,
  "note": "傍晚散步",
  "checkedAt": "2026-09-04T10:00:00Z"
}
```

第一版只保存用户输入的地点名与坐标，不进行反向地理编码，也不关联照片或笔记对象；这些能力留给后续阶段。
