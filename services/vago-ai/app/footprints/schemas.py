"""旅行足迹接口的请求与响应模型。"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _serialize_utc_datetime(value: datetime) -> str:
    """将 MySQL naive UTC DATETIME 显式序列化为带 Z 的 API 时间。"""
    # 分支条件：数据库返回无时区 DATETIME 时，按项目约定补为 UTC；已有时区则统一转换为 UTC。
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc_value.isoformat().replace("+00:00", "Z")


class LocationSampleInput(BaseModel):
    """移动端离线队列中的单个 GPS 样本。"""

    # 客户端生成的稳定 UUID，作为幂等键。
    client_uuid: str = Field(alias="clientUuid", min_length=1, max_length=64)
    # 纬度，范围为 WGS-84 合法值。
    latitude: float = Field(ge=-90, le=90)
    # 经度，范围为 WGS-84 合法值。
    longitude: float = Field(ge=-180, le=180)
    # 水平定位精度，单位米；未知时可不传。
    accuracy_m: float | None = Field(default=None, alias="accuracyM", ge=0, le=100_000)
    # 移动速度，单位米/秒；未知时可不传。
    speed_mps: float | None = Field(default=None, alias="speedMps", ge=0, le=500)
    # 设备记录时间。
    recorded_at: datetime = Field(alias="recordedAt")

    model_config = ConfigDict(populate_by_name=True)


class LocationSyncRequest(BaseModel):
    """一次最多同步 100 条 GPS 样本，便于网络恢复时分批重试。"""

    # 目标正式行程 UUID。
    trip_uuid: str = Field(alias="tripUuid", min_length=1, max_length=32)
    # 待同步的本地样本队列。
    samples: list[LocationSampleInput] = Field(min_length=1, max_length=100)

    model_config = ConfigDict(populate_by_name=True)


class LocationSyncResponse(BaseModel):
    """批量同步结果。"""

    # 本次请求中实际新写入的样本数量。
    accepted_count: int = Field(alias="acceptedCount")
    # 因客户端幂等键已存在而跳过的样本数量。
    duplicate_count: int = Field(alias="duplicateCount")

    model_config = ConfigDict(populate_by_name=True)


class LocationSampleResponse(BaseModel):
    """用于 MapKit 渲染的已持久化轨迹点。"""

    # 服务端位置记录 UUID。
    uuid: str
    # 纬度。
    latitude: float
    # 经度。
    longitude: float
    # 定位精度，单位米。
    accuracy_m: float | None = Field(default=None, alias="accuracyM")
    # 移动速度，单位米/秒。
    speed_mps: float | None = Field(default=None, alias="speedMps")
    # 实际采样时间。
    recorded_at: datetime = Field(alias="recordedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("recorded_at")
    def serialize_recorded_at(self, value: datetime) -> str:
        """保证 MapKit 客户端收到可明确解析的 UTC 采样时间。"""
        return _serialize_utc_datetime(value)


class CheckinCreateRequest(BaseModel):
    """用户手动创建打卡的请求。"""

    # 打卡归属的正式行程 UUID。
    trip_uuid: str = Field(alias="tripUuid", min_length=1, max_length=32)
    # 用户可编辑的地点名称。
    location_name: str = Field(alias="locationName", min_length=1, max_length=256)
    # 打卡纬度。
    latitude: float = Field(ge=-90, le=90)
    # 打卡经度。
    longitude: float = Field(ge=-180, le=180)
    # 可选旅行笔记。
    note: str | None = Field(default=None, max_length=2000)
    # 客户端触发时间；未传时服务端使用当前 UTC 时间。
    checked_at: datetime | None = Field(default=None, alias="checkedAt")

    model_config = ConfigDict(populate_by_name=True)


class CheckinResponse(BaseModel):
    """手动打卡响应。"""

    # 打卡业务 UUID。
    uuid: str
    # 关联正式行程 UUID。
    trip_uuid: str = Field(alias="tripUuid")
    # 地点名称。
    location_name: str = Field(alias="locationName")
    # 纬度。
    latitude: float
    # 经度。
    longitude: float
    # 用户笔记。
    note: str | None = None
    # 打卡时间。
    checked_at: datetime = Field(alias="checkedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        """保证手动打卡响应的时间携带 UTC 时区信息。"""
        return _serialize_utc_datetime(value)
