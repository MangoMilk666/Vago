from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError


class PlanningConstraint(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    value: Any
    scope: str | None = None
    day: int | None = None


class PlanningBrief(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    start_date: date | None = Field(default=None, validation_alias=AliasChoices("startDate", "start_date"))
    end_date: date | None = Field(default=None, validation_alias=AliasChoices("endDate", "end_date"))
    timezone_name: str | None = Field(default=None, validation_alias=AliasChoices("timezone", "timeZone"))
    party_size: int = Field(default=1, ge=1, validation_alias=AliasChoices("partySize", "party_size"))
    budget_currency: str | None = Field(default=None, validation_alias=AliasChoices("budgetCurrency", "budget_currency"))
    hard_constraints: list[PlanningConstraint] = Field(
        default_factory=list, validation_alias=AliasChoices("hardConstraints", "constraints")
    )


class PlanningItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: str = Field(default="custom", validation_alias=AliasChoices("kind", "type"))
    city: str = ""
    start_time: str | None = Field(default=None, validation_alias=AliasChoices("startTime", "start_time"))
    end_time: str | None = Field(default=None, validation_alias=AliasChoices("endTime", "end_time"))
    end_date: date | None = Field(default=None, validation_alias=AliasChoices("endDate", "end_date"))
    duration_minutes: int | None = Field(
        default=None, ge=0, validation_alias=AliasChoices("durationMinutes", "duration_minutes")
    )
    price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    tags: list[str] | None = None
    source_url: str | None = Field(default=None, validation_alias=AliasChoices("sourceUrl", "source_url"))


class PlanningLeg(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_item_id: str | None = Field(default=None, validation_alias=AliasChoices("fromItemId", "fromPointId"))
    to_item_id: str | None = Field(default=None, validation_alias=AliasChoices("toItemId", "toPointId"))
    route_duration_minutes: int | None = Field(default=None, ge=0, validation_alias="routeDurationMinutes")
    duration_minutes: int | None = Field(default=None, ge=0, validation_alias=AliasChoices("durationMinutes", "minutes"))
    buffer_minutes: int = Field(default=0, ge=0, validation_alias="bufferMinutes")
    provider: str | None = None
    queried_at: datetime | None = Field(default=None, validation_alias="queriedAt")
    route_choice_id: str | None = Field(default=None, validation_alias="routeChoiceId")


class PlanningDay(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    day: int = Field(ge=1)
    on_date: date | None = Field(default=None, validation_alias=AliasChoices("date", "onDate", "on_date"))
    city: str = ""
    timezone_name: str | None = Field(default=None, validation_alias=AliasChoices("timezone", "timeZone"))
    start_time: str | None = Field(default=None, validation_alias="startTime")
    items: list[PlanningItem] = Field(default_factory=list)
    legs: list[PlanningLeg] = Field(default_factory=list)
    note: str = ""


class PlanningContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    days: list[PlanningDay] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


def _check(code: str, status: str, message: str, *, blocking: bool = True,
           day: int | None = None, item_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "severity": "blocking" if blocking else "warning",
        "message": message,
        "day": day,
        "itemIds": item_ids or [],
    }


def _clock(value: str) -> time:
    if len(value) != 5 or value[2] != ":" or not value[:2].isdigit() or not value[3:].isdigit():
        raise ValueError("时间必须使用 HH:MM")
    return time(hour=int(value[:2]), minute=int(value[3:]))


def _local_time(day: date, value: str, zone: ZoneInfo) -> datetime:
    local = datetime.combine(day, _clock(value))
    aware = local.replace(tzinfo=zone)
    # 如果时钟位于夏令时跳变或重复时段，缺少偏移量时无法确定唯一时刻。
    if aware.utcoffset() != local.replace(tzinfo=zone, fold=1).utcoffset():
        raise ValueError("当地时间处于夏令时切换时段，需提供明确偏移量")
    if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != local:
        raise ValueError("当地时间在该时区不存在")
    return aware


def _minutes(leg: PlanningLeg) -> int | None:
    # 如果同时有路线耗时与总耗时，两者必须与缓冲时间一致。
    if leg.route_duration_minutes is not None:
        total = leg.route_duration_minutes + leg.buffer_minutes
        if leg.duration_minutes is not None and leg.duration_minutes != total:
            raise ValueError("交通总耗时与路线耗时加缓冲时间不一致")
        return total
    return leg.duration_minutes


def _mentions(text: str, word: str) -> bool:
    if not text or not word:
        return False
    negators = ("不含", "没有", "免", "无", "不", "没", "非", "去")
    start = 0
    while (index := text.find(word, start)) >= 0:
        if not any(text[:index].endswith(negator) for negator in negators):
            return True
        start = index + 1
    return False


def _budget(days: list[PlanningDay], party_size: int, currency: str | None,
            limit: Decimal) -> tuple[str, str]:
    total = Decimal(0)
    missing = 0
    carried_hotel: PlanningItem | None = None
    for day in days[:-1]:
        hotel = next((item for item in day.items if item.kind == "hotel"), None)
        if hotel is not None:
            carried_hotel = hotel
        if carried_hotel is None or carried_hotel.price is None or (
            (carried_hotel.currency or "").strip().upper() != currency.strip().upper()
        ):
            missing += 1
        else:
            total += carried_hotel.price
    for day in days:
        for item in day.items:
            if item.kind not in {"restaurant", "attraction"}:
                continue
            if item.price is None or (item.currency or "").strip().upper() != currency.strip().upper():
                missing += 1
            else:
                total += item.price * party_size
    if total > limit:
        return "fail", f"已知费用 {total} {currency} 超过上限 {limit}"
    if missing:
        return "unverifiable", f"有 {missing} 项缺少价格或币种，已知费用 {total} {currency}"
    return "pass", f"费用合计 {total} {currency}，上限 {limit}"


def _adapt_content(content_data: dict[str, Any], brief: PlanningBrief) -> dict[str, Any]:
    """把 wkf 的 snapshot 或 points/routes 视图映射到同一候选校验输入。"""
    if "days" in content_data:
        return content_data
    snapshot = content_data.get("snapshot")
    if "snapshot" in content_data:
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("days"), list):
            raise ValueError("wkf 快照结构无效")
        days = []
        for day in snapshot["days"]:
            if not isinstance(day, dict) or not isinstance(day.get("items"), list):
                raise ValueError("wkf 每日安排结构无效")
            converted = dict(day)
            items = []
            for item in day["items"]:
                if not isinstance(item, dict):
                    raise ValueError("wkf 地点结构无效")
                point = dict(item)
                # 如果输入是 wkf Snapshot，wkf 的价格契约固定为人民币。
                if point.get("price") is not None and "currency" not in point:
                    point["currency"] = "CNY"
                items.append(point)
            converted["items"] = items
            days.append(converted)
        return {"days": days, "gaps": snapshot.get("gaps", [])}
    points = content_data.get("points")
    if "points" not in content_data:
        return content_data
    if not isinstance(points, list):
        raise ValueError("wkf 地点列表结构无效")
    grouped: dict[int, dict[str, Any]] = {}
    for point in points:
        if not isinstance(point, dict) or type(point.get("day")) is not int or point["day"] < 1:
            raise ValueError("wkf 地点缺少有效日序")
        day_number = point["day"]
        day = grouped.setdefault(day_number, {"day": day_number, "items": [], "legs": []})
        if brief.start_date:
            day["date"] = (brief.start_date + timedelta(days=day_number - 1)).isoformat()
        day["items"].append({
            "id": point.get("id"), "name": point.get("name"), "kind": point.get("type", "custom"),
            "city": point.get("city", ""), "startTime": point.get("startTime"),
            "endTime": point.get("endTime"), "durationMinutes": point.get("durationMinutes"),
            "price": point.get("price"), "currency": point.get("currency"),
            "tags": point.get("tags"), "sourceUrl": point.get("sourceUrl"),
        })
    routes = content_data.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("wkf 路线列表结构无效")
    for route in routes:
        if not isinstance(route, dict) or type(route.get("day")) is not int or route["day"] not in grouped:
            raise ValueError("wkf 路线缺少有效日序")
        segments = route.get("segments") or []
        if not isinstance(segments, list):
            raise ValueError("wkf 路线分段结构无效")
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("wkf 路线分段结构无效")
            grouped[route["day"]]["legs"].append({
                "fromPointId": segment.get("fromPointId"), "toPointId": segment.get("toPointId"),
                "routeDurationMinutes": segment.get("routeDurationMinutes"),
                "durationMinutes": segment.get("durationMinutes"),
                "bufferMinutes": segment.get("bufferMinutes", 0),
                "routeChoiceId": segment.get("routeChoiceId"),
                "queriedAt": segment.get("queriedAt"), "provider": segment.get("provider"),
            })
    return {"days": list(grouped.values()), "gaps": content_data.get("gaps", [])}


def _timeline(days: list[PlanningDay], brief: PlanningBrief) -> tuple[list[dict[str, Any]], dict[int, list[datetime | None]]]:
    checks: list[dict[str, Any]] = []
    endings: dict[int, list[datetime | None]] = {}
    for day in days:
        zone_name = day.timezone_name or brief.timezone_name
        if not zone_name or day.on_date is None:
            checks.append(_check("timeline", "unverifiable", "缺少日期或时区", day=day.day))
            continue
        try:
            zone = ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            checks.append(_check("timeline", "fail", "时区名称无效", day=day.day))
            continue
        by_pair = {(leg.from_item_id, leg.to_item_id): leg for leg in day.legs
                   if leg.from_item_id and leg.to_item_id}
        expected_pairs = [(left.id, right.id) for left, right in zip(day.items, day.items[1:])]
        referenced = [leg for leg in day.legs if leg.from_item_id and leg.to_item_id]
        if len(by_pair) != len(referenced):
            checks.append(_check("route_order", "fail", "同一相邻地点之间出现重复路线", day=day.day))
        if len(referenced) != len(day.legs):
            checks.append(_check("route_order", "unverifiable", "路线缺少唯一的地点 ID", day=day.day))
        if any(pair not in expected_pairs for pair in by_pair):
            checks.append(_check("route_order", "fail", "路线起终点与相邻地点顺序不一致", day=day.day))
        previous_end: datetime | None = None
        day_endings: list[datetime | None] = []
        for index, item in enumerate(day.items):
            try:
                start = _local_time(day.on_date, item.start_time, zone) if item.start_time else None
                end = _local_time(item.end_date or day.on_date, item.end_time, zone) if item.end_time else None
                if index == 0 and start is None and day.start_time:
                    start = _local_time(day.on_date, day.start_time, zone)
                if index:
                    pair = expected_pairs[index - 1]
                    leg = by_pair.get(pair)
                    if leg is None:
                        checks.append(_check("route", "unverifiable", "相邻地点之间缺少路线", day=day.day,
                                             item_ids=list(pair)))
                    else:
                        travel = _minutes(leg)
                        described = (
                            leg.route_duration_minutes is not None
                            and bool(leg.provider and leg.route_choice_id)
                            and leg.queried_at is not None
                            and leg.queried_at.tzinfo is not None
                        )
                        if not described:
                            checks.append(_check("route", "unverifiable", "路线缺少耗时或来源标识", day=day.day,
                                                 item_ids=list(pair)))
                        if described and previous_end is not None and travel is not None:
                            earliest = previous_end + timedelta(minutes=travel)
                            if start is None:
                                start = earliest
                            elif start < earliest:
                                checks.append(_check("timeline", "fail", "抵达时间晚于固定开始时间", day=day.day,
                                                     item_ids=[item.id]))
                    if previous_end is not None and start is not None and start < previous_end:
                        checks.append(_check("timeline", "fail", "日程时间发生重叠", day=day.day,
                                             item_ids=[item.id]))
                if end is None and start is not None and item.duration_minutes is not None:
                    end = start + timedelta(minutes=item.duration_minutes)
                if start is None or end is None:
                    checks.append(_check("timeline", "unverifiable", "地点缺少可计算的起止时间", day=day.day,
                                         item_ids=[item.id]))
                elif end < start:
                    checks.append(_check("timeline", "fail", "结束时间早于开始时间；跨日须明确 endDate", day=day.day,
                                         item_ids=[item.id]))
                elif item.duration_minutes is not None and end - start != timedelta(minutes=item.duration_minutes):
                    checks.append(_check("timeline", "fail", "起止时间与停留时长不一致", day=day.day,
                                         item_ids=[item.id]))
                previous_end = end
                day_endings.append(end)
            except ValueError as exc:
                checks.append(_check("timeline", "fail", str(exc), day=day.day, item_ids=[item.id]))
                previous_end = None
                day_endings.append(None)
        endings[day.day] = day_endings
    if not checks:
        checks.append(_check("timeline", "pass", "日程时间、停留和相邻路线顺序一致"))
    return checks, endings


def _constraint(constraint: PlanningConstraint, days: list[PlanningDay], brief: PlanningBrief,
                endings: dict[int, list[datetime | None]], content: PlanningContent) -> dict[str, Any]:
    kind = constraint.type
    rule = f"constraint:{kind}"
    selected = [day for day in days if constraint.day is None or day.day == constraint.day]
    if not selected:
        return _check(rule, "unverifiable", "指定日期不在候选行程中")
    value = constraint.value
    if kind == "days_count":
        if type(value) is not int or value < 0:
            return _check(rule, "fail", "天数约束必须是非负整数")
        return _check(rule, "pass" if len(days) == value else "fail", f"候选 {len(days)} 天，要求 {value} 天")
    if kind == "budget_total_max":
        try:
            if isinstance(value, bool) or not Decimal(str(value)).is_finite() or Decimal(str(value)) < 0:
                raise ValueError
            limit = Decimal(str(value))
        except (ValueError, ArithmeticError):
            return _check(rule, "fail", "预算上限必须是非负金额")
        if not brief.budget_currency:
            return _check(rule, "unverifiable", "缺少预算币种，不能合计价格")
        status, message = _budget(days, brief.party_size, brief.budget_currency, limit)
        return _check(rule, status, message)
    if kind == "day_end_before":
        if not isinstance(value, str):
            return _check(rule, "fail", "结束时间上限必须是 HH:MM")
        try:
            limit = _clock(value)
        except ValueError as exc:
            return _check(rule, "fail", str(exc))
        for day in selected:
            values = endings.get(day.day)
            if values and day.on_date and any(
                end.date() > day.on_date or end.time() > limit for end in values if end
            ):
                return _check(rule, "fail", f"第 {day.day} 天超过 {value} 结束", day=day.day)
            if not values or any(end is None for end in values):
                return _check(rule, "unverifiable", "缺少完整结束时间", day=day.day)
        return _check(rule, "pass", f"指定日期均在 {value} 前结束")
    if kind == "max_transit_minutes":
        if type(value) is not int or value < 0:
            return _check(rule, "fail", "交通时间上限必须是非负整数")
        all_legs = [leg for day in selected for leg in day.legs]
        expected = sum(max(len(day.items) - 1, 0) for day in selected)
        try:
            times = [_minutes(leg) for leg in all_legs]
        except ValueError as exc:
            return _check(rule, "fail", str(exc))
        if len(all_legs) != expected or any(
            leg.route_duration_minutes is None or not leg.provider or not leg.route_choice_id
            or leg.queried_at is None or leg.queried_at.tzinfo is None
            for leg in all_legs
        ):
            return _check(rule, "unverifiable", "路线或来源不足，不能核对单段交通时间")
        if any(minutes > value for minutes in times):
            return _check(rule, "fail", f"有单段交通超过 {value} 分钟")
        return _check(rule, "pass", f"每段交通均不超过 {value} 分钟")
    if kind == "max_poi_per_day":
        if type(value) is not int or value < 0:
            return _check(rule, "fail", "景点数量上限必须是非负整数")
        over = [day.day for day in selected if sum(item.kind == "attraction" for item in day.items) > value]
        return _check(rule, "fail" if over else "pass", f"超限日期：{over}" if over else "景点数量符合上限")
    if kind == "must_cover_cities":
        if not isinstance(value, list) or not value or not all(isinstance(city, str) and city.strip() for city in value):
            return _check(rule, "fail", "城市约束必须是非空城市列表")
        cities = {day.city.strip().casefold() for day in days if day.city.strip()}
        if not cities:
            return _check(rule, "unverifiable", "候选没有提供每日城市")
        missing = [city for city in value if city.strip().casefold() not in cities]
        return _check(rule, "fail" if missing else "pass", f"未覆盖城市：{missing}" if missing else "已覆盖指定城市")
    if kind in {"must_not_contain_category", "must_include_tag"}:
        if not isinstance(value, str) or not value.strip():
            return _check(rule, "fail", "禁忌或标签必须是非空文字")
        items = [item for day in selected for item in day.items]
        if kind == "must_include_tag":
            if not constraint.scope:
                return _check(rule, "fail", "标签约束缺少适用类别")
            items = [item for item in items if item.kind == constraint.scope]
            if not items:
                return _check(rule, "fail", "候选没有要求的地点类别")
            missing = [item.id for item in items if item.tags is not None and not any(
                _mentions(tag, value) for tag in item.tags
            )]
            if missing:
                return _check(rule, "fail", "地点未满足要求标签", item_ids=missing)
            if any(item.tags is None for item in items):
                return _check(rule, "unverifiable", "地点缺少标签证据")
            return _check(rule, "pass", "地点标签满足要求")
        hits = [item.id for item in items if _mentions(item.name, value) or any(
            _mentions(tag, value) for tag in item.tags or []
        )]
        if hits:
            return _check(rule, "fail", "候选包含明确禁忌", item_ids=hits)
        if any(item.tags is None for item in items):
            return _check(rule, "unverifiable", "地点缺少标签，无法排除禁忌")
        return _check(rule, "pass", "候选未包含指定禁忌")
    if kind == "must_report_gaps":
        if value is not True:
            return _check(rule, "fail", "信息缺口约束的值必须为 true")
        missing = [item for day in days for item in day.items if not item.source_url]
        status = "pass" if content.gaps or not missing else "fail"
        return _check(rule, status, "已说明信息缺口" if status == "pass" else "无来源地点未说明信息缺口")
    return _check(rule, "unverifiable", f"尚无 {kind} 的确定性判定规则")


def validate_proposal(brief_data: dict[str, Any], content_data: dict[str, Any]) -> dict[str, Any]:
    """依据候选原文生成确定性报告；不访问模型、地图服务或正式旅行表。"""
    try:
        brief = PlanningBrief.model_validate(brief_data)
        content = PlanningContent.model_validate(_adapt_content(content_data, brief))
    except (ValidationError, ValueError):
        # 如果结构字段类型不对，保留候选原文，但明确标记为不能确认的版本。
        return {"schemaVersion": 1, "scope": "deterministic_candidate_data", "outcome": "fail",
                "hardChecksPassed": False,
                "checks": [_check("schema", "fail", "候选字段结构无效")], "warnings": []}
    checks: list[dict[str, Any]] = []
    days = sorted(content.days, key=lambda day: day.day)
    if not days:
        checks.append(_check("days", "unverifiable", "候选没有每日安排"))
    else:
        numbers = [day.day for day in days]
        if numbers != list(range(1, len(days) + 1)):
            checks.append(_check("days", "fail", "日序必须从 1 开始连续且不能重复"))
        ids = [item.id for day in days for item in day.items]
        if len(ids) != len(set(ids)):
            checks.append(_check("item_ids", "fail", "地点 ID 在候选中重复"))
        if any(not day.items for day in days):
            checks.append(_check("days", "unverifiable", "存在没有地点的日期"))
    if brief.start_date is None or brief.end_date is None:
        checks.append(_check("date_range", "unverifiable", "缺少旅行开始或结束日期"))
    elif brief.start_date > brief.end_date:
        checks.append(_check("date_range", "fail", "旅行结束日期早于开始日期"))
    else:
        expected = (brief.end_date - brief.start_date).days + 1
        if len(days) != expected or any(
            day.on_date != brief.start_date + timedelta(days=day.day - 1) for day in days
        ):
            checks.append(_check("date_range", "fail", "每日日期与旅行起止日期不一致"))
        else:
            checks.append(_check("date_range", "pass", "每日日期覆盖完整旅行区间"))
    timeline, endings = _timeline(days, brief)
    checks.extend(timeline)
    for day in days[:-1]:
        hotels = [item for item in day.items if item.kind == "hotel"]
        if not hotels:
            checks.append(_check("accommodation", "unverifiable", "该晚没有住宿资料", blocking=False, day=day.day))
        elif any(item.city and day.city and item.city != day.city for item in hotels):
            checks.append(_check("accommodation", "fail", "住宿与当日城市不一致", day=day.day))
    if any(not item.source_url for day in days for item in day.items):
        checks.append(_check("sources", "unverifiable", "部分地点没有来源", blocking=False))
    if any(day.legs for day in days):
        # 如果路线只由客户端提交，当前阶段无法核实它是否真实来自所写的 provider。
        checks.append(_check("route_provenance", "unverifiable", "路线尚未经过服务端来源核验"))
    for constraint in brief.hard_constraints:
        checks.append(_constraint(constraint, days, brief, endings, content))
    blocking = [item for item in checks if item["severity"] == "blocking" and item["status"] != "pass"]
    outcome = "fail" if any(item["status"] == "fail" for item in blocking) else (
        "unverifiable" if blocking else "pass"
    )
    return {"schemaVersion": 1, "scope": "deterministic_candidate_data", "outcome": outcome,
            "hardChecksPassed": not blocking,
            "checks": checks, "warnings": list(content.gaps)}
