"""为 Travel Footprint 开发调试生成可重复的空间观察数据。"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from math import asin, cos, pi, sqrt
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.footprints.models import TravelObservation
from app.footprints.service import (
    AUTO_GPS,
    MANUAL_CHECKIN,
    MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS,
    MINIMUM_CHECKIN_DISTANCE_METERS,
)
from app.travel.models import Trip


DEV_SEED_PREFIX = "devseed:"
_RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
DEFAULT_GPS_SPACING_METERS = 25.0
MIN_GPS_SPACING_METERS = 20.0
MAX_GPS_SPACING_METERS = 100.0
DEFAULT_CHECKIN_COUNT = 6
MAX_CHECKIN_COUNT = 12
GPS_SAMPLE_INTERVAL_MINUTES = 2
DEFAULT_DAY_HOURS = 8.0
MIN_DAY_HOURS = 6.0
MAX_DAY_HOURS = 12.0
SEGMENT_BREAK_MINUTES = 45
PROXIMITY_SEGMENT_DURATION_MINUTES = 30
PROXIMITY_SEGMENT_GAP_MINUTES = 30
EARTH_RADIUS_METERS = 6_371_000.0


@dataclass(frozen=True)
class Waypoint:
    """测试路线中的一个 WGS-84 锚点。"""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class CheckinTemplate:
    """测试场景中用户主动确认的地点信息。"""

    name: str
    note: str
    latitude: float
    longitude: float
    segment_index: int
    minute_offset: int


@dataclass(frozen=True)
class FootprintScenario:
    """一组适合验证地图渲染与上下文读取的固定旅行区域。"""

    code: str
    title: str
    segments: tuple[tuple[Waypoint, ...], ...]
    checkins: tuple[CheckinTemplate, ...]
    start_at: datetime


@dataclass(frozen=True)
class GeneratedObservation:
    """尚未持久化的测试空间观察，便于单元测试与 CLI 共用。"""

    observation_type: str
    latitude: float
    longitude: float
    occurred_at: datetime
    tracking_segment_uuid: str | None
    location_name: str | None = None
    note: str | None = None
    accuracy_m: float | None = None
    speed_mps: float | None = None


def _waypoints(*coordinates: tuple[float, float]) -> tuple[Waypoint, ...]:
    """将简短坐标字面量转换为不可变路线锚点。"""
    return tuple(Waypoint(latitude, longitude) for latitude, longitude in coordinates)


SCENARIOS: dict[str, FootprintScenario] = {
    "MARINA_SANDS_BAY": FootprintScenario(
        code="MARINA_SANDS_BAY",
        title="新加坡滨海湾步行",
        segments=(
            _waypoints((1.2838, 103.8600), (1.2845, 103.8616), (1.2854, 103.8635)),
            _waypoints((1.2862, 103.8652), (1.2869, 103.8669), (1.2881, 103.8682)),
        ),
        checkins=(
            CheckinTemplate("滨海湾金沙", "傍晚从空中花园俯瞰海湾。", 1.2839, 103.8605, 0, 8),
            CheckinTemplate("滨海湾花园", "夜间灯光秀前抵达。", 1.2816, 103.8636, 1, 34),
        ),
        start_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
    ),
    "CA_TAHOE": FootprintScenario(
        code="CA_TAHOE",
        title="太浩湖环湖自驾",
        segments=(
            _waypoints((39.0968, -120.0324), (39.0984, -120.0267), (39.1012, -120.0208)),
            _waypoints((39.1075, -120.0130), (39.1120, -120.0067), (39.1164, -119.9992)),
        ),
        checkins=(
            CheckinTemplate("翡翠湾观景台", "湖水颜色很通透，适合停留拍照。", 38.9530, -120.1058, 0, 10),
            CheckinTemplate("Sand Harbor", "下午在湖岸短暂停留。", 39.2005, -120.1207, 1, 42),
        ),
        start_at=datetime(2026, 8, 12, 15, 0, tzinfo=UTC),
    ),
    "LONDON": FootprintScenario(
        code="LONDON",
        title="伦敦泰晤士河步行",
        segments=(
            _waypoints((51.5007, -0.1246), (51.5011, -0.1218), (51.5015, -0.1188)),
            _waypoints((51.5021, -0.1145), (51.5030, -0.1105), (51.5040, -0.1067)),
        ),
        checkins=(
            CheckinTemplate("大本钟", "从威斯敏斯特桥开始沿河步行。", 51.5007, -0.1246, 0, 3),
            CheckinTemplate("泰特现代美术馆", "傍晚抵达河对岸的展馆。", 51.5076, -0.0994, 1, 38),
        ),
        start_at=datetime(2026, 4, 18, 10, 0, tzinfo=UTC),
    ),
    "TOKYO_SHIBUYA": FootprintScenario(
        code="TOKYO_SHIBUYA",
        title="东京涩谷步行",
        segments=(
            _waypoints((35.6595, 139.7005), (35.6608, 139.7019), (35.6620, 139.7036)),
            _waypoints((35.6641, 139.7044), (35.6652, 139.7023), (35.6667, 139.6998)),
        ),
        checkins=(
            CheckinTemplate("涩谷十字路口", "人流最密集的路口，适合观察城市节奏。", 35.6595, 139.7005, 0, 4),
            CheckinTemplate("代代木公园", "午后散步休息。", 35.6717, 139.6949, 1, 31),
        ),
        start_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
    ),
    "PARIS_SEINE": FootprintScenario(
        code="PARIS_SEINE",
        title="巴黎塞纳河步行",
        segments=(
            _waypoints((48.8585, 2.2946), (48.8588, 2.3002), (48.8594, 2.3055)),
            _waypoints((48.8600, 2.3133), (48.8607, 2.3204), (48.8612, 2.3267)),
        ),
        checkins=(
            CheckinTemplate("埃菲尔铁塔", "晨间从战神广场出发。", 48.8584, 2.2945, 0, 3),
            CheckinTemplate("奥赛博物馆", "沿河步行后的室内停留。", 48.8600, 2.3266, 1, 38),
        ),
        start_at=datetime(2026, 6, 4, 8, 30, tzinfo=UTC),
    ),
    "ICELAND_REYKJAVIK": FootprintScenario(
        code="ICELAND_REYKJAVIK",
        title="雷克雅未克城市漫步",
        segments=(
            _waypoints((64.1466, -21.9426), (64.1476, -21.9393), (64.1486, -21.9358)),
            _waypoints((64.1500, -21.9329), (64.1510, -21.9294), (64.1519, -21.9257)),
        ),
        checkins=(
            CheckinTemplate("哈尔格林姆斯教堂", "在高处查看港湾方向。", 64.1417, -21.9266, 0, 6),
            CheckinTemplate("Harpa 音乐厅", "傍晚沿港口散步。", 64.1500, -21.9324, 1, 35),
        ),
        start_at=datetime(2026, 5, 22, 17, 0, tzinfo=UTC),
    ),
    "CHECKIN_PROXIMITY": FootprintScenario(
        code="CHECKIN_PROXIMITY",
        title="临近打卡采样验证",
        segments=(
            _waypoints((1.2901, 103.8510), (1.2903, 103.8512), (1.2906, 103.8515)),
            _waypoints((1.2912, 103.8521), (1.2916, 103.8525), (1.2920, 103.8529)),
        ),
        checkins=(
            CheckinTemplate("测试近距打卡", "用于验证自动采样避让手动打卡。", 1.2903, 103.8512, 0, 3),
        ),
        start_at=datetime(2026, 9, 2, 14, 0, tzinfo=UTC),
    ),
}

# 保留首版讨论中出现的单数 Sand 写法，CLI 内部仍统一使用规范场景 code。
LOCATION_ALIASES = {"MARINA_SAND_BAY": "MARINA_SANDS_BAY"}


def available_locations() -> tuple[str, ...]:
    """返回 CLI 可选的固定场景 code。"""
    return tuple(SCENARIOS)


def build_scenario_observations(
    location: str,
    seed: int,
    *,
    gps_spacing_meters: float = DEFAULT_GPS_SPACING_METERS,
    checkin_count: int = DEFAULT_CHECKIN_COUNT,
    day_hours: float = DEFAULT_DAY_HOURS,
) -> list[GeneratedObservation]:
    """将固定路线细分为覆盖一天的不规则 GPS 轨迹和多处手动打卡。"""
    scenario = _get_scenario(location)
    _validate_generation_options(gps_spacing_meters, checkin_count, day_hours)
    randomizer = random.Random(seed)
    observations: list[GeneratedObservation] = []
    checkins = list(scenario.checkins)
    if scenario.code != "CHECKIN_PROXIMITY":
        checkins.extend(_build_supplemental_checkins(scenario, checkins, checkin_count, day_hours))

    for segment_index, waypoints in enumerate(scenario.segments):
        segment_uuid = str(uuid5(NAMESPACE_URL, f"vago-devseed:{scenario.code}:{seed}:segment:{segment_index}"))
        segment_start, segment_duration = _segment_schedule(
            scenario,
            segment_index,
            day_hours,
        )
        segment_samples = _build_segment_observations(
            waypoints,
            segment_start,
            segment_uuid,
            randomizer,
            gps_spacing_meters,
        )
        # 如果是普通场景，移除落在手动打卡保护半径内的自动点，保持真实采样规则。
        if scenario.code != "CHECKIN_PROXIMITY":
            segment_samples = [
                sample for sample in segment_samples
                if all(
                    _distance_meters(sample.latitude, sample.longitude, checkin.latitude, checkin.longitude)
                    >= MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS
                    for checkin in checkins
                )
            ]
        segment_samples = _spread_sample_times(segment_samples, segment_start, segment_duration)
        observations.extend(segment_samples)

    for checkin in checkins:
        segment_uuid = str(uuid5(NAMESPACE_URL, f"vago-devseed:{scenario.code}:{seed}:segment:{checkin.segment_index}"))
        segment_start, _ = _segment_schedule(scenario, checkin.segment_index, day_hours)
        observations.append(GeneratedObservation(
            observation_type=MANUAL_CHECKIN,
            latitude=checkin.latitude,
            longitude=checkin.longitude,
            occurred_at=segment_start + timedelta(minutes=checkin.minute_offset),
            tracking_segment_uuid=segment_uuid,
            location_name=checkin.name,
            note=checkin.note,
        ))

    return sorted(observations, key=lambda item: (item.occurred_at, item.observation_type))


def _segment_schedule(
    scenario: FootprintScenario,
    segment_index: int,
    day_hours: float,
) -> tuple[datetime, timedelta]:
    """为每段轨迹计算一天内的开始时间和活动时长。"""
    # 如果是近距边界场景，保留短时间间隔，便于验证专用边界样本。
    if scenario.code == "CHECKIN_PROXIMITY":
        offset_minutes = segment_index * (PROXIMITY_SEGMENT_DURATION_MINUTES + PROXIMITY_SEGMENT_GAP_MINUTES)
        return (
            scenario.start_at + timedelta(minutes=offset_minutes),
            timedelta(minutes=PROXIMITY_SEGMENT_DURATION_MINUTES),
        )

    segment_count = len(scenario.segments)
    total_duration = timedelta(hours=day_hours)
    total_breaks = timedelta(minutes=SEGMENT_BREAK_MINUTES * max(0, segment_count - 1))
    active_duration = (total_duration - total_breaks) / segment_count
    segment_offset = (active_duration + timedelta(minutes=SEGMENT_BREAK_MINUTES)) * segment_index
    return scenario.start_at + segment_offset, active_duration


def _spread_sample_times(
    samples: list[GeneratedObservation],
    segment_start: datetime,
    segment_duration: timedelta,
) -> list[GeneratedObservation]:
    """把该段有序 GPS 点均匀放到活动时段，令默认数据覆盖整日多时段。"""
    # 如果该段只有一个有效点，将时间设为段起点，避免除以零。
    if len(samples) <= 1:
        return [replace(sample, occurred_at=segment_start) for sample in samples]
    last_offset = segment_duration.total_seconds()
    last_index = len(samples) - 1
    return [
        replace(
            sample,
            occurred_at=segment_start + timedelta(seconds=last_offset * index / last_index),
        )
        for index, sample in enumerate(samples)
    ]


def _build_segment_observations(
    waypoints: tuple[Waypoint, ...],
    started_at: datetime,
    segment_uuid: str,
    randomizer: random.Random,
    spacing_meters: float,
) -> list[GeneratedObservation]:
    """按空间间距细分相邻锚点，并保留可渲染的连续采样顺序。"""
    observations: list[GeneratedObservation] = []
    point_index = 0
    for start, end in zip(waypoints, waypoints[1:]):
        leg_distance = _distance_meters(start.latitude, start.longitude, end.latitude, end.longitude)
        step_count = max(1, int(leg_distance // spacing_meters) + 1)
        for step in range(step_count):
            ratio = step / step_count
            latitude = start.latitude + (end.latitude - start.latitude) * ratio
            longitude = start.longitude + (end.longitude - start.longitude) * ratio
            # 将米级随机偏移转为经纬度，避免测试路线呈现为机械的绝对直线。
            latitude, longitude = _jitter_coordinate(latitude, longitude, randomizer)
            # 如果相邻锚点距离或取整导致相邻候选太近，跳过该点以符合自动采样距离边界。
            if observations and _distance_meters(
                observations[-1].latitude,
                observations[-1].longitude,
                latitude,
                longitude,
            ) < MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS:
                continue
            observations.append(GeneratedObservation(
                observation_type=AUTO_GPS,
                latitude=latitude,
                longitude=longitude,
                occurred_at=started_at + timedelta(minutes=point_index * GPS_SAMPLE_INTERVAL_MINUTES),
                tracking_segment_uuid=segment_uuid,
                accuracy_m=round(randomizer.uniform(4.0, 10.0), 1),
                speed_mps=round(randomizer.uniform(0.8, 1.8), 2),
            ))
            point_index += 1
    endpoint = waypoints[-1]
    endpoint_latitude, endpoint_longitude = _jitter_coordinate(
        endpoint.latitude,
        endpoint.longitude,
        randomizer,
    )
    # 如果路线末端与上一采样点过近，保留上一点作为该段末端，避免制造重复近距样本。
    if not observations or _distance_meters(
        observations[-1].latitude,
        observations[-1].longitude,
        endpoint_latitude,
        endpoint_longitude,
    ) >= MINIMUM_AUTOMATIC_SAMPLE_DISTANCE_TO_CHECKIN_METERS:
        observations.append(GeneratedObservation(
            observation_type=AUTO_GPS,
            latitude=endpoint_latitude,
            longitude=endpoint_longitude,
            occurred_at=started_at + timedelta(minutes=point_index * GPS_SAMPLE_INTERVAL_MINUTES),
            tracking_segment_uuid=segment_uuid,
            accuracy_m=round(randomizer.uniform(4.0, 10.0), 1),
            speed_mps=round(randomizer.uniform(0.8, 1.8), 2),
        ))
    return observations


def _build_supplemental_checkins(
    scenario: FootprintScenario,
    existing: list[CheckinTemplate],
    requested_count: int,
    day_hours: float,
) -> list[CheckinTemplate]:
    """沿固定路线补充相互满足最小间距的模拟手动打卡。"""
    added: list[CheckinTemplate] = []
    candidate_count = max(requested_count * 8, 48)
    for candidate_index in range(1, candidate_count):
        # 如果已经达到目标打卡数，不再检查更多候选路线位置。
        if len(existing) + len(added) >= requested_count:
            break
        segment_index = candidate_index % len(scenario.segments)
        fraction = candidate_index / candidate_count
        waypoints = scenario.segments[segment_index]
        latitude, longitude = _interpolate_route_point(waypoints, fraction)
        # 如果候选点距离已有手动打卡不足 30 米，跳过以遵循服务端的防重复范围。
        if any(
            _distance_meters(latitude, longitude, checkin.latitude, checkin.longitude)
            < MINIMUM_CHECKIN_DISTANCE_METERS
            for checkin in (*existing, *added)
        ):
            continue
        _, segment_duration = _segment_schedule(scenario, segment_index, day_hours)
        added.append(CheckinTemplate(
            name=f"{scenario.title}沿途打卡 {len(existing) + len(added) + 1}",
            note="开发测试模拟点，用于验证地图打卡标注与详情展示。",
            latitude=latitude,
            longitude=longitude,
            segment_index=segment_index,
            minute_offset=int(segment_duration.total_seconds() / 60 * fraction),
        ))
    return added


def _interpolate_route_point(waypoints: tuple[Waypoint, ...], fraction: float) -> tuple[float, float]:
    """按路线累计距离而非锚点数量，在折线路径上取一个候选坐标。"""
    leg_lengths = [
        _distance_meters(start.latitude, start.longitude, end.latitude, end.longitude)
        for start, end in zip(waypoints, waypoints[1:])
    ]
    total_length = sum(leg_lengths)
    target_distance = total_length * fraction
    traversed = 0.0
    for (start, end), leg_length in zip(zip(waypoints, waypoints[1:]), leg_lengths):
        if target_distance <= traversed + leg_length:
            ratio = (target_distance - traversed) / max(leg_length, 1.0)
            return (
                start.latitude + (end.latitude - start.latitude) * ratio,
                start.longitude + (end.longitude - start.longitude) * ratio,
            )
        traversed += leg_length
    return waypoints[-1].latitude, waypoints[-1].longitude


def _distance_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """使用 Haversine 公式计算两个 WGS-84 坐标间的地表距离。"""
    latitude_delta = (latitude_b - latitude_a) * pi / 180
    longitude_delta = (longitude_b - longitude_a) * pi / 180
    latitude_a_radians = latitude_a * pi / 180
    latitude_b_radians = latitude_b * pi / 180
    haversine = (
        (1 - cos(latitude_delta)) / 2
        + cos(latitude_a_radians) * cos(latitude_b_radians) * (1 - cos(longitude_delta)) / 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(min(1.0, max(0.0, haversine))))


def _validate_generation_options(gps_spacing_meters: float, checkin_count: int, day_hours: float) -> None:
    """校验空间密度、打卡数量与一天内时间跨度。"""
    # 如果 GPS 点间距超出开发工具允许范围，拒绝生成过稀或违反近距规则的数据。
    if not MIN_GPS_SPACING_METERS <= gps_spacing_meters <= MAX_GPS_SPACING_METERS:
        raise ValueError(
            f"--gps-spacing-meters 必须在 {MIN_GPS_SPACING_METERS:g} 到 {MAX_GPS_SPACING_METERS:g} 米之间"
        )
    # 如果打卡数量超出边界，拒绝生成不适合地图调试的大批重复地点。
    if not 1 <= checkin_count <= MAX_CHECKIN_COUNT:
        raise ValueError(f"--checkin-count 必须在 1 到 {MAX_CHECKIN_COUNT} 之间")
    # 如果日内时间跨度超出 6-12 小时，拒绝生成难以解释为单日行程的数据。
    if not MIN_DAY_HOURS <= day_hours <= MAX_DAY_HOURS:
        raise ValueError(f"--day-hours 必须在 {MIN_DAY_HOURS:g} 到 {MAX_DAY_HOURS:g} 小时之间")


def _jitter_coordinate(latitude: float, longitude: float, randomizer: random.Random) -> tuple[float, float]:
    """将最多约两米的确定性偏移换算成 WGS-84 坐标。"""
    latitude_offset_m = randomizer.uniform(-2.0, 2.0)
    longitude_offset_m = randomizer.uniform(-2.0, 2.0)
    latitude_delta = latitude_offset_m / 111_111
    longitude_delta = longitude_offset_m / max(1.0, 111_111 * cos(latitude * pi / 180))
    return latitude + latitude_delta, longitude + longitude_delta


def seed_footprints(
    db: Session,
    *,
    user_uuid: str,
    trip_uuid: str,
    location: str,
    seed: int,
    run_id: str,
    replace: bool = False,
    gps_spacing_meters: float = DEFAULT_GPS_SPACING_METERS,
    checkin_count: int = DEFAULT_CHECKIN_COUNT,
    day_hours: float = DEFAULT_DAY_HOURS,
) -> dict[str, int | str]:
    """为指定用户和 Trip 写入一个可追踪、可重复清理的测试场景。"""
    _validate_run_id(run_id)
    _get_owned_trip(db, user_uuid, trip_uuid)
    existing_count = _count_run_observations(db, user_uuid, trip_uuid, run_id)
    # 如果同一 run 已存在且未明确允许替换，阻止重复写入影响地图读数。
    if existing_count and not replace:
        raise ValueError(f"测试 run '{run_id}' 已存在，请使用 --replace 或 --clear-run")
    if existing_count:
        _clear_run_observations(db, user_uuid, trip_uuid, run_id)

    generated = build_scenario_observations(
        location,
        seed,
        gps_spacing_meters=gps_spacing_meters,
        checkin_count=checkin_count,
        day_hours=day_hours,
    )
    rows = [
        TravelObservation(
            uuid=uuid5(NAMESPACE_URL, f"vago-devseed:{user_uuid}:{trip_uuid}:{run_id}:{index}").hex,
            client_event_uuid=f"{DEV_SEED_PREFIX}{run_id}:{index}",
            user_uuid=user_uuid,
            trip_uuid=trip_uuid,
            observation_type=item.observation_type,
            latitude=item.latitude,
            longitude=item.longitude,
            accuracy_m=item.accuracy_m,
            speed_mps=item.speed_mps,
            tracking_segment_uuid=item.tracking_segment_uuid,
            location_name=item.location_name,
            note=item.note,
            occurred_at=item.occurred_at.astimezone(UTC).replace(tzinfo=None),
        )
        for index, item in enumerate(generated)
    ]
    db.add_all(rows)
    db.commit()
    return {
        "location": _get_scenario(location).code,
        "run_id": run_id,
        "observation_count": len(rows),
        "automatic_sample_count": sum(row.observation_type == AUTO_GPS for row in rows),
        "checkin_count": sum(row.observation_type == MANUAL_CHECKIN for row in rows),
    }


def clear_seed_run(db: Session, *, user_uuid: str, trip_uuid: str, run_id: str) -> int:
    """仅删除指定 run 标记的测试观察，绝不影响真实或其他 run 的数据。"""
    _validate_run_id(run_id)
    _get_owned_trip(db, user_uuid, trip_uuid)
    deleted_count = _clear_run_observations(db, user_uuid, trip_uuid, run_id)
    db.commit()
    return deleted_count


def _get_scenario(location: str) -> FootprintScenario:
    """读取规范化后的场景；未知 code 时列出可用选项。"""
    normalized_location = LOCATION_ALIASES.get(location.upper(), location.upper())
    scenario = SCENARIOS.get(normalized_location)
    # 如果 location 不是预置场景，拒绝写入以保证每套测试数据有明确语义。
    if scenario is None:
        available = ", ".join(available_locations())
        raise ValueError(f"未知 --location '{location}'，可选值：{available}")
    return scenario


def _parse_location(value: str) -> str:
    """供 argparse 使用的场景解析器，兼容大小写与历史别名。"""
    try:
        return _get_scenario(value).code
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _get_owned_trip(db: Session, user_uuid: str, trip_uuid: str) -> Trip:
    """确认 CLI 不会向不存在、已删除或其他用户的 Trip 写入测试事实。"""
    trip = db.scalar(select(Trip).where(
        Trip.uuid == trip_uuid,
        Trip.user_uuid == user_uuid,
        Trip.deleted_at.is_(None),
    ))
    # 如果目标 Trip 不属于指定用户，统一拒绝，避免开发工具破坏数据隔离。
    if trip is None:
        raise ValueError("Trip 不存在、已删除或不属于指定 user_uuid")
    return trip


def _run_prefix(run_id: str) -> str:
    """返回用于精准筛选测试数据的客户端事件键前缀。"""
    return f"{DEV_SEED_PREFIX}{run_id}:"


def _count_run_observations(db: Session, user_uuid: str, trip_uuid: str, run_id: str) -> int:
    """统计同一测试 run 已写入的观察数量。"""
    return len(db.scalars(select(TravelObservation.id).where(
        TravelObservation.user_uuid == user_uuid,
        TravelObservation.trip_uuid == trip_uuid,
        TravelObservation.client_event_uuid.startswith(_run_prefix(run_id)),
    )).all())


def _clear_run_observations(db: Session, user_uuid: str, trip_uuid: str, run_id: str) -> int:
    """删除同一 user、Trip 和 run 前缀下的测试观察。"""
    result = db.execute(delete(TravelObservation).where(
        TravelObservation.user_uuid == user_uuid,
        TravelObservation.trip_uuid == trip_uuid,
        TravelObservation.client_event_uuid.startswith(_run_prefix(run_id)),
    ))
    return result.rowcount or 0


def _validate_run_id(run_id: str) -> None:
    """限制 run id 的字符集，保证 SQL 前缀筛选与事件键长度可控。"""
    # 如果 run id 不满足安全字符和长度限制，拒绝生成或清理操作。
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("--run-id 只能使用小写字母、数字和连字符，长度 1-31")


def _parse_args() -> argparse.Namespace:
    """解析 CLI 参数；通过 --clear-run 在不生成新数据时定向清理。"""
    parser = argparse.ArgumentParser(description="生成仅限本地开发使用的 Travel Footprint 测试数据")
    parser.add_argument("--user-uuid", required=True)
    parser.add_argument("--trip-uuid", required=True)
    parser.add_argument("--location", type=_parse_location, metavar="LOCATION")
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument(
        "--gps-spacing-meters",
        type=float,
        default=DEFAULT_GPS_SPACING_METERS,
        help=f"自动 GPS 样本的目标间距，允许 {MIN_GPS_SPACING_METERS:g}-{MAX_GPS_SPACING_METERS:g} 米",
    )
    parser.add_argument(
        "--checkin-count",
        type=int,
        default=DEFAULT_CHECKIN_COUNT,
        help=f"普通场景的目标手动打卡数量，允许 1-{MAX_CHECKIN_COUNT}",
    )
    parser.add_argument(
        "--day-hours",
        type=float,
        default=DEFAULT_DAY_HOURS,
        help=f"普通场景覆盖的日内时长，允许 {MIN_DAY_HOURS:g}-{MAX_DAY_HOURS:g} 小时",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--replace", action="store_true", help="仅替换同一 run-id 的既有测试数据")
    parser.add_argument("--clear-run", action="store_true", help="仅删除同一 run-id 的测试数据，不生成新数据")
    args = parser.parse_args()
    # 如果是生成操作且参数越界，在连接数据库前终止，避免产生部分开发数据。
    if not args.clear_run:
        try:
            _validate_generation_options(args.gps_spacing_meters, args.checkin_count, args.day_hours)
        except ValueError as exc:
            parser.error(str(exc))
    # 如果未指定 run-id，使用 location 和 seed 构造稳定、可重复的默认标识。
    if not args.run_id:
        if args.clear_run and not args.location:
            parser.error("--clear-run 需要同时提供 --run-id，或提供 --location 以推导默认 run-id")
        location = (args.location or "footprint").lower().replace("_", "-")
        args.run_id = f"{location}-{args.seed}"
    # 如果不是清理动作，必须选择一个固定旅游区域。
    if not args.clear_run and not args.location:
        parser.error("生成测试数据需要 --location")
    return args


def main() -> None:
    """CLI 入口：仅在 local/development 环境连接数据库并写入测试事实。"""
    args = _parse_args()
    # 如果当前环境不是本地开发环境，拒绝执行，避免测试工具进入生产数据库。
    if settings.environment.lower() not in {"local", "development"}:
        raise SystemExit("seed_footprints 仅允许在 environment=local 或 development 时运行")

    with SessionLocal() as db:
        if args.clear_run:
            deleted_count = clear_seed_run(
                db,
                user_uuid=args.user_uuid,
                trip_uuid=args.trip_uuid,
                run_id=args.run_id,
            )
            print(json.dumps({"run_id": args.run_id, "deleted_count": deleted_count}, ensure_ascii=False))
            return
        summary = seed_footprints(
            db,
            user_uuid=args.user_uuid,
            trip_uuid=args.trip_uuid,
            location=args.location,
            seed=args.seed,
            run_id=args.run_id,
            replace=args.replace,
            gps_spacing_meters=args.gps_spacing_meters,
            checkin_count=args.checkin_count,
            day_hours=args.day_hours,
        )
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
