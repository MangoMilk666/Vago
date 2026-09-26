"""为 Travel Footprint 开发调试生成可重复的空间观察数据。"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import cos, pi
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.footprints.models import TravelObservation
from app.footprints.service import AUTO_GPS, MANUAL_CHECKIN
from app.travel.models import Trip


DEV_SEED_PREFIX = "devseed:"
_RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


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


def build_scenario_observations(location: str, seed: int) -> list[GeneratedObservation]:
    """将固定路线插值为带轻微偏移的确定性 GPS 与手动打卡观察。"""
    scenario = _get_scenario(location)
    randomizer = random.Random(seed)
    observations: list[GeneratedObservation] = []

    for segment_index, waypoints in enumerate(scenario.segments):
        segment_uuid = str(uuid5(NAMESPACE_URL, f"vago-devseed:{scenario.code}:{seed}:segment:{segment_index}"))
        segment_start = scenario.start_at + timedelta(minutes=segment_index * 30)
        observations.extend(_build_segment_observations(waypoints, segment_start, segment_uuid, randomizer))

    for checkin in scenario.checkins:
        segment_uuid = str(uuid5(NAMESPACE_URL, f"vago-devseed:{scenario.code}:{seed}:segment:{checkin.segment_index}"))
        observations.append(GeneratedObservation(
            observation_type=MANUAL_CHECKIN,
            latitude=checkin.latitude,
            longitude=checkin.longitude,
            occurred_at=scenario.start_at + timedelta(minutes=checkin.minute_offset),
            tracking_segment_uuid=segment_uuid,
            location_name=checkin.name,
            note=checkin.note,
        ))

    return sorted(observations, key=lambda item: (item.occurred_at, item.observation_type))


def _build_segment_observations(
    waypoints: tuple[Waypoint, ...],
    started_at: datetime,
    segment_uuid: str,
    randomizer: random.Random,
) -> list[GeneratedObservation]:
    """在相邻锚点间生成连续点位，并注入远小于采样间距的坐标偏移。"""
    observations: list[GeneratedObservation] = []
    point_index = 0
    for start, end in zip(waypoints, waypoints[1:]):
        for step in range(8):
            ratio = step / 8
            latitude = start.latitude + (end.latitude - start.latitude) * ratio
            longitude = start.longitude + (end.longitude - start.longitude) * ratio
            # 将米级随机偏移转为经纬度，避免测试路线呈现为机械的绝对直线。
            latitude, longitude = _jitter_coordinate(latitude, longitude, randomizer)
            observations.append(GeneratedObservation(
                observation_type=AUTO_GPS,
                latitude=latitude,
                longitude=longitude,
                occurred_at=started_at + timedelta(minutes=point_index * 2),
                tracking_segment_uuid=segment_uuid,
                accuracy_m=round(randomizer.uniform(4.0, 10.0), 1),
                speed_mps=round(randomizer.uniform(0.8, 1.8), 2),
            ))
            point_index += 1
    return observations


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

    generated = build_scenario_observations(location, seed)
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
    parser.add_argument("--run-id")
    parser.add_argument("--replace", action="store_true", help="仅替换同一 run-id 的既有测试数据")
    parser.add_argument("--clear-run", action="store_true", help="仅删除同一 run-id 的测试数据，不生成新数据")
    args = parser.parse_args()
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
        )
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
