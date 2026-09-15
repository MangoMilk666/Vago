"""Travel Observation 的 SQLAlchemy 模型。

自动 GPS 与用户手动打卡都属于不可变的旅行空间观察；两者共用位置、时间和归属，
但通过 observation_type 保留主动确认打卡的名称、备注等业务语义。
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class TravelObservation(Base):
    """用户旅行过程中记录的一条空间事实。"""

    __tablename__ = "travel_observations"
    # 所有观察都使用客户端事件键，离线 GPS 重试与手动打卡重复提交都可幂等处理。
    __table_args__ = (UniqueConstraint("user_uuid", "client_event_uuid", name="uk_travel_observations_user_client"),)

    # 数据库内部主键。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 服务端生成并对外暴露的观察 UUID。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 客户端预先生成的稳定事件键，用于同一用户范围内幂等去重。
    client_event_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    # 归属用户，用于严格数据隔离。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 关联正式行程 UUID。
    trip_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # AUTO_GPS 或 MANUAL_CHECKIN，决定采样规则和地图展示语义。
    observation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    # WGS-84 纬度。
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    # WGS-84 经度。
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # 自动 GPS 可携带水平精度；手动打卡允许为空。
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    # 自动 GPS 可携带速度；手动打卡允许为空。
    speed_mps: Mapped[float | None] = mapped_column(Float)
    # 连续前台记录段；未开启记录时创建的手动打卡为空，避免伪造路线连线。
    tracking_segment_uuid: Mapped[str | None] = mapped_column(String(36))
    # MANUAL_CHECKIN 的用户确认地点名称；自动 GPS 为空。
    location_name: Mapped[str | None] = mapped_column(String(256))
    # MANUAL_CHECKIN 的可选旅行笔记；自动 GPS 为空。
    note: Mapped[str | None] = mapped_column(Text)
    # 观察实际发生时间，统一替代旧 recorded_at / checked_at。
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 服务端首次持久化时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
