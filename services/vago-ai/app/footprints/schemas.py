"""旅行空间观察接口的请求与响应模型。"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


ObservationType = Literal["AUTO_GPS", "MANUAL_CHECKIN"]


def _serialize_utc_datetime(value: datetime) -> str:
    """将 MySQL naive UTC DATETIME 显式序列化为带 Z 的 API 时间。"""
    # 分支条件：数据库返回无时区 DATETIME 时，按项目约定补为 UTC；已有时区则统一转换为 UTC。
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc_value.isoformat().replace("+00:00", "Z")


class LocationSampleInput(BaseModel):
    """移动端离线队列中的单个自动 GPS 样本。"""

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
    # 连续前台记录的段标识；旧客户端可省略，服务端不为历史样本补造边界。
    tracking_segment_uuid: str | None = Field(default=None, alias="trackingSegmentUuid", min_length=1, max_length=36)
    # 设备记录时间。
    recorded_at: datetime = Field(alias="recordedAt")

    model_config = ConfigDict(populate_by_name=True)


class LocationSyncRequest(BaseModel):
    """一次最多同步 100 条自动 GPS 样本。"""

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
    # 因附近已有手动打卡而不需要保存的自动样本数量，客户端可安全移除对应待传项。
    skipped_count: int = Field(alias="skippedCount")

    model_config = ConfigDict(populate_by_name=True)


class TravelObservationResponse(BaseModel):
    """地图与 Live Context 共用的统一旅行空间观察。"""

    uuid: str
    client_event_uuid: str = Field(alias="clientEventUuid")
    trip_uuid: str = Field(alias="tripUuid")
    observation_type: ObservationType = Field(alias="observationType")
    latitude: float
    longitude: float
    accuracy_m: float | None = Field(default=None, alias="accuracyM")
    speed_mps: float | None = Field(default=None, alias="speedMps")
    tracking_segment_uuid: str | None = Field(default=None, alias="trackingSegmentUuid")
    location_name: str | None = Field(default=None, alias="locationName")
    note: str | None = None
    occurred_at: datetime = Field(alias="occurredAt")

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("occurred_at")
    def serialize_occurred_at(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class LocationSampleResponse(BaseModel):
    """兼容旧地图读取入口的自动 GPS 响应。"""

    uuid: str
    client_uuid: str = Field(alias="clientUuid")
    latitude: float
    longitude: float
    accuracy_m: float | None = Field(default=None, alias="accuracyM")
    speed_mps: float | None = Field(default=None, alias="speedMps")
    tracking_segment_uuid: str | None = Field(default=None, alias="trackingSegmentUuid")
    recorded_at: datetime = Field(alias="recordedAt")

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("recorded_at")
    def serialize_recorded_at(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)


class CheckinCreateRequest(BaseModel):
    """用户手动创建打卡的请求。"""

    trip_uuid: str = Field(alias="tripUuid", min_length=1, max_length=32)
    # 新客户端提供事件键以防止重复提交；旧客户端未提供时服务端仍可兼容创建。
    client_event_uuid: str | None = Field(default=None, alias="clientEventUuid", min_length=1, max_length=64)
    location_name: str = Field(alias="locationName", min_length=1, max_length=256)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=2000)
    tracking_segment_uuid: str | None = Field(default=None, alias="trackingSegmentUuid", min_length=1, max_length=36)
    checked_at: datetime | None = Field(default=None, alias="checkedAt")

    model_config = ConfigDict(populate_by_name=True)


class CheckinUpdateRequest(BaseModel):
    """用户对手动打卡补充或修正的可编辑语义字段。"""

    # 地点名称属于用户主动输入的注释，可编辑但不能清空。
    location_name: str = Field(alias="locationName", min_length=1, max_length=256)
    # 空字符串由服务层规范化为 NULL，表示用户主动清除备注。
    note: str = Field(default="", max_length=2000)

    model_config = ConfigDict(populate_by_name=True)


class CheckinResponse(BaseModel):
    """兼容既有打卡入口的手动打卡响应。"""

    uuid: str
    trip_uuid: str = Field(alias="tripUuid")
    location_name: str = Field(alias="locationName")
    latitude: float
    longitude: float
    note: str | None = None
    checked_at: datetime = Field(alias="checkedAt")

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        return _serialize_utc_datetime(value)
