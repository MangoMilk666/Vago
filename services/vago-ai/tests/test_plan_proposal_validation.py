import json
from pathlib import Path

from app.plan_proposals.validation import validate_proposal


SAMPLE_PATH = Path(__file__).resolve().parents[3] / "docs/project-merge/phase-0/planning-sample.json"


def _brief() -> dict:
    return {
        "startDate": "2026-11-01", "endDate": "2026-11-02", "timezone": "Asia/Singapore",
        "partySize": 2, "budgetCurrency": "SGD",
        "hardConstraints": [
            {"type": "days_count", "value": 2},
            {"type": "budget_total_max", "value": 250},
            {"type": "day_end_before", "value": "20:00"},
            {"type": "must_cover_cities", "value": ["Singapore"]},
        ],
    }


def _content() -> dict:
    return {"days": [
        {"day": 1, "date": "2026-11-01", "city": "Singapore", "items": [
            {"id": "hotel-1", "name": "住宿", "kind": "hotel", "city": "Singapore",
             "startTime": "18:00", "endTime": "18:30", "price": 100, "currency": "SGD", "tags": ["电梯"]},
        ]},
        {"day": 2, "date": "2026-11-02", "city": "Singapore", "items": [
            {"id": "place-2", "name": "景点", "kind": "attraction", "city": "Singapore",
             "startTime": "09:00", "endTime": "10:00", "price": 50, "currency": "SGD", "tags": ["室内"]},
        ]},
    ]}


def _status(report: dict, code: str) -> str:
    return next(item["status"] for item in report["checks"] if item["code"] == code)


def test_validation_reuses_wkf_budget_and_daily_snapshot_rules():
    """测试：多日、住宿按晚和门票按人数计价的候选得到可回读的确定性结果。"""
    report = validate_proposal(_brief(), _content())
    assert report["outcome"] == "pass"
    assert report["hardChecksPassed"] is True
    assert _status(report, "constraint:budget_total_max") == "pass"
    assert _status(report, "constraint:days_count") == "pass"


def test_validation_blocks_missing_price_and_known_budget_excess():
    """测试：缺价格不按零计算；已知费用超预算时直接失败。"""
    content = _content()
    content["days"][1]["items"][0]["price"] = None
    report = validate_proposal(_brief(), content)
    assert _status(report, "constraint:budget_total_max") == "unverifiable"
    assert report["hardChecksPassed"] is False

    content["days"][1]["items"][0]["price"] = 100
    report = validate_proposal(_brief(), content)
    assert _status(report, "constraint:budget_total_max") == "fail"


def test_validation_checks_route_order_gap_and_fixed_time_conflict():
    """测试：相邻地点缺路线、路线指向错误与固定到达时间冲突分别可判定。"""
    brief = _brief()
    content = _content()
    content["days"][1]["items"].append({
        "id": "meal-2", "name": "午餐", "kind": "restaurant", "city": "Singapore",
        "startTime": "10:10", "endTime": "11:00", "price": 10, "currency": "SGD", "tags": [],
    })
    missing = validate_proposal(brief, content)
    assert _status(missing, "route") == "unverifiable"

    content["days"][1]["legs"] = [{
        "fromItemId": "meal-2", "toItemId": "place-2", "routeDurationMinutes": 15,
        "bufferMinutes": 5, "provider": "amap", "routeChoiceId": "route-1",
        "queriedAt": "2026-10-26T09:00:00+08:00",
    }]
    wrong_order = validate_proposal(brief, content)
    assert _status(wrong_order, "route_order") == "fail"

    content["days"][1]["legs"][0].update({"fromItemId": "place-2", "toItemId": "meal-2"})
    conflict = validate_proposal(brief, content)
    assert _status(conflict, "timeline") == "fail"
    assert _status(conflict, "route_provenance") == "unverifiable"


def test_validation_requires_explicit_cross_midnight_date_and_handles_daily_timezone():
    """测试：跨午夜必须标明次日日期；不同旅行日可各自采用当地时区。"""
    brief = _brief()
    brief["hardConstraints"] = []
    content = _content()
    content["days"][0]["timezone"] = "Asia/Shanghai"
    content["days"][1]["timezone"] = "Asia/Tokyo"
    content["days"][1]["items"][0].update({
        "startTime": "23:30", "endTime": "00:30", "endDate": "2026-11-03", "durationMinutes": 60,
    })
    assert validate_proposal(brief, content)["hardChecksPassed"] is True
    del content["days"][1]["items"][0]["endDate"]
    assert _status(validate_proposal(brief, content), "timeline") == "fail"


def test_validation_keeps_unknown_and_forbidden_constraints_blocking():
    """测试：未知硬规则无法验证；明确禁忌命中失败，否定标签不误判为命中。"""
    brief = _brief()
    brief["hardConstraints"] = [{"type": "must_not_contain_category", "value": "海鲜"}]
    content = _content()
    content["days"][1]["items"][0]["tags"] = ["不含海鲜"]
    assert _status(validate_proposal(brief, content), "constraint:must_not_contain_category") == "pass"
    content["days"][1]["items"][0]["tags"] = ["含海鲜"]
    assert _status(validate_proposal(brief, content), "constraint:must_not_contain_category") == "fail"
    brief["hardConstraints"] = [{"type": "unsupported_rule", "value": True}]
    assert _status(validate_proposal(brief, content), "constraint:unsupported_rule") == "unverifiable"


def test_validation_accepts_wkf_snapshot_without_claiming_route_provenance():
    """测试：wkf 快照可适配日期与预算规则；只有名称的旧路线仍明确无法核验。"""
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    brief = {"startDate": "2026-11-01", "endDate": "2026-11-01",
             "timezone": "Asia/Shanghai", "budgetCurrency": "CNY",
             "hardConstraints": sample["constraints"]}
    report = validate_proposal(brief, {"snapshot": sample["snapshot"]})
    assert _status(report, "constraint:days_count") == "pass"
    assert _status(report, "constraint:budget_total_max") == "pass"
    assert _status(report, "route_order") == "unverifiable"
