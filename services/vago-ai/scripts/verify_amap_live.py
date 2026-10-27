import asyncio
from datetime import datetime

from app.plan_proposals.providers import (
    PlaceSearchRequest, RouteSearchRequest, search_places, search_routes, verify_route_token,
)


async def main() -> None:
    """使用公开景点核对本机高德服务配置及真实路线响应。"""
    origin_results = await search_places(PlaceSearchRequest(countryCode="CN", city="上海", query="外滩"))
    destination_results = await search_places(PlaceSearchRequest(countryCode="CN", city="上海", query="东方明珠"))
    if not origin_results or not destination_results:
        raise RuntimeError("高德地点搜索没有返回验收所需的两个景点")
    origin, destination = origin_results[0], destination_results[0]
    print(f"地点搜索：起点 {origin['name']}，终点 {destination['name']}")
    for mode in ("walking", "driving", "transit"):
        payload = RouteSearchRequest(
            countryCode="CN", city="上海", cityCode=origin.get("cityCode"), mode=mode,
            fromItemId=origin["id"], toItemId=destination["id"],
            originLatitude=origin["latitude"], originLongitude=origin["longitude"],
            destinationLatitude=destination["latitude"], destinationLongitude=destination["longitude"],
            coordinateSystem="GCJ-02",
        )
        routes = await search_routes(payload, "phase-4-live-check")
        print(f"{mode}：{len(routes)} 条路线，首条 {routes[0]['routeDurationMinutes']} 分钟")
        first = routes[0]
        verified = verify_route_token(
            first["routeChoiceId"], "phase-4-live-check", origin["id"], destination["id"],
            first["routeDurationMinutes"], first["provider"], datetime.fromisoformat(first["queriedAt"]),
            mode, first["coordinateSystem"],
            [origin["latitude"], origin["longitude"]],
            [destination["latitude"], destination["longitude"]],
        )
        if not verified:
            raise RuntimeError(f"{mode} 路线来源签名校验失败")


if __name__ == "__main__":
    asyncio.run(main())
