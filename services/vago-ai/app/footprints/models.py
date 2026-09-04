"""Travel Footprint 的 SQLAlchemy 模型。

第一版只保存 GPS 采样和手动打卡两类不可变事实，不提前引入分区、GIS 或地图瓦片等复杂基础设施。
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.travel.models import utc_now_naive


class LocationSample(Base):
    """移动端采集的一条 GPS 位置样本。"""

    __tablename__ = "location_samples"
    # 同一用户的同一客户端样本只接受一次，使离线重试不会重复写入轨迹。
    __table_args__ = (UniqueConstraint("user_uuid", "client_uuid", name="uk_location_samples_user_client"),)

    # 数据库内部主键。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 服务端生成并对外暴露的位置记录 UUID。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # iOS 本地预先生成的 UUID，用于批量同步幂等。
    client_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    # 记录所属用户，用于严格的数据隔离。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 关联正式行程 UUID。
    trip_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # WGS-84 纬度。
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    # WGS-84 经度。
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # 采样时定位系统报告的水平精度，单位米。
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    # 采样时移动速度，单位米/秒。
    speed_mps: Mapped[float | None] = mapped_column(Float)
    # 设备实际记录时间，服务端不使用接收时间代替它。
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 服务端首次持久化时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class Checkin(Base):
    """用户主动确认的一次旅行打卡。"""

    __tablename__ = "checkins"

    # 数据库内部主键。
    id: Mapped[int] = mapped_column(primary_key=True)
    # 打卡业务 UUID。
    uuid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 打卡所属用户。
    user_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 打卡关联的正式行程 UUID。
    trip_uuid: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # 用户填写或客户端提供的地点名称。
    location_name: Mapped[str] = mapped_column(String(256), nullable=False)
    # 打卡坐标纬度。
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    # 打卡坐标经度。
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # 用户补充的简短旅行笔记。
    note: Mapped[str | None] = mapped_column(Text)
    # 用户触发打卡的实际时间。
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 服务端首次持久化时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
