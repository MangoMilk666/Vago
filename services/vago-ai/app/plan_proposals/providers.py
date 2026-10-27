import math
import time
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import jwt
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.redis import get_redis_client


class PlaceSearchRequest(BaseModel):
    country_code: str = Field(alias="countryCode", min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=120)


class RouteSearchRequest(BaseModel):
    country_code: str = Field(alias="countryCode", min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=80)
    city_code: str | None = Field(default=None, alias="cityCode", pattern=r"^[0-9]{3,6}$")
    mode: Literal["walking", "driving", "transit"]
    from_item_id: str = Field(alias="fromItemId", min_length=1, max_length=100)
    to_item_id: str = Field(alias="toItemId", min_length=1, max_length=100)
    origin_latitude: float = Field(alias="originLatitude", ge=-90, le=90)
    origin_longitude: float = Field(alias="originLongitude", ge=-180, le=180)
    destination_latitude: float = Field(alias="destinationLatitude", ge=-90, le=90)
    destination_longitude: float = Field(alias="destinationLongitude", ge=-180, le=180)
    coordinate_system: Literal["GCJ-02", "WGS84"] = Field(alias="coordinateSystem")


def provider_for(country_code: str) -> str:
    """判断目标地区应由哪个地点与路线来源负责。"""
    code = country_code.upper()
    if code not in {"CN", "SG", "HK", "GB", "US"}:
        raise AppException("当前尚未开放该地区的规划地点与路线查询", status_code=422,
                           code="MAP_REGION_UNSUPPORTED")
    return "amap" if code == "CN" else "apple_maps"


async def enforce_provider_quota(user_uuid: str) -> None:
    """限制每位用户的外部地图请求，避免共享服务配额被持续耗尽。"""
    key = f"vago:planning-provider:{user_uuid}:{int(time.time()) // 60}"
    try:
        redis = await get_redis_client()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 65)
    except RedisError as exc:
        raise AppException("地图查询配额校验暂时不可用", status_code=503,
                           code="MAP_QUOTA_UNAVAILABLE") from exc
    if count > 12:
        raise AppException("地图查询过于频繁，请稍后再试", status_code=429,
                           code="MAP_USER_RATE_LIMITED")


async def _get(url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException as exc:
        raise AppException("地图服务请求超时", status_code=503, code="MAP_PROVIDER_TIMEOUT") from exc
    except httpx.HTTPStatusError as exc:
        status = 429 if exc.response.status_code == 429 else 503
        raise AppException("地图服务配额不足或暂时不可用", status_code=status,
                           code="MAP_PROVIDER_UNAVAILABLE") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise AppException("地图服务响应不可用", status_code=503, code="MAP_PROVIDER_UNAVAILABLE") from exc
    if not isinstance(result, dict):
        raise AppException("地图服务响应结构无效", status_code=503, code="MAP_PROVIDER_INVALID_RESPONSE")
    return result


async def _apple_access_token() -> str:
    if not all((settings.apple_maps_team_id, settings.apple_maps_key_id, settings.apple_maps_private_key)):
        raise AppException("Apple Maps Server API 尚未配置", status_code=503, code="APPLE_MAPS_NOT_CONFIGURED")
    now = int(time.time())
    private_key = settings.apple_maps_private_key.replace("\\n", "\n")
    signed = jwt.encode(
        {"iss": settings.apple_maps_team_id, "iat": now, "exp": now + 600, "scope": "server_api"},
        private_key, algorithm="ES256", headers={"kid": settings.apple_maps_key_id, "typ": "JWT"},
    )
    data = await _get("https://maps-api.apple.com/v1/token", {}, {"Authorization": f"Bearer {signed}"})
    token = data.get("accessToken")
    if not isinstance(token, str) or not token:
        raise AppException("Apple Maps 未返回访问令牌", status_code=503, code="MAP_PROVIDER_INVALID_RESPONSE")
    return token


async def _request(provider: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    if provider == "amap":
        if not settings.amap_web_key:
            raise AppException("高德 Web 服务尚未配置", status_code=503, code="AMAP_NOT_CONFIGURED")
        data = await _get(f"https://restapi.amap.com{path}", {"key": settings.amap_web_key, **params})
        if str(data.get("status")) != "1":
            # 如果高德返回业务错误，保留数字错误码，便于区分参数、权限和额度问题。
            infocode = str(data.get("infocode", ""))
            detail = f"（错误码 {infocode}）" if infocode.isdecimal() else ""
            raise AppException(f"高德未能完成查询{detail}", status_code=503,
                               code="MAP_PROVIDER_UNAVAILABLE")
        return data
    token = await _apple_access_token()
    return await _get(f"https://maps-api.apple.com{path}", params, {"Authorization": f"Bearer {token}"})


async def search_places(payload: PlaceSearchRequest) -> list[dict[str, Any]]:
    provider = provider_for(payload.country_code)
    if provider == "amap":
        data = await _request(provider, "/v3/place/text", {
            "keywords": payload.query, "city": payload.city, "citylimit": "true", "offset": 10,
        })
        places = []
        for poi in data.get("pois") or []:
            location = poi.get("location")
            if not isinstance(location, str) or "," not in location:
                continue
            longitude, latitude = (float(part) for part in location.split(",", 1))
            places.append({"id": poi.get("id"), "name": poi.get("name"),
                           "latitude": latitude, "longitude": longitude,
                           "coordinateSystem": "GCJ-02", "provider": provider,
                           "cityCode": poi.get("citycode"),
                           "address": poi.get("address")})
        return places
    data = await _request(provider, "/v1/search", {
        "q": payload.query, "limitToCountries": payload.country_code.upper(),
    })
    places = []
    for place in data.get("results") or []:
        coordinate = place.get("coordinate") or {}
        if coordinate.get("latitude") is None or coordinate.get("longitude") is None:
            continue
        places.append({"id": place.get("id"), "name": place.get("name"),
                       "latitude": coordinate["latitude"], "longitude": coordinate["longitude"],
                       "coordinateSystem": "WGS84", "provider": provider,
                       "address": ", ".join(place.get("formattedAddressLines") or [])})
    return places


def _route_token(user_uuid: str, payload: RouteSearchRequest, provider: str,
                 duration_minutes: int, queried_at: str, route_index: int) -> str:
    if not settings.jwt_secret_key:
        raise AppException("路线引用签名密钥尚未配置", status_code=503, code="ROUTE_SIGNING_NOT_CONFIGURED")
    # 如果候选在十分钟后才提交，路线时效已无法保证，必须重新查询。
    return jwt.encode({
        "typ": "planning_route", "sub": user_uuid, "provider": provider,
        "from": payload.from_item_id, "to": payload.to_item_id,
        "minutes": duration_minutes, "queriedAt": queried_at,
        "routeIndex": route_index,
        "mode": payload.mode, "coordinateSystem": payload.coordinate_system,
        "origin": [payload.origin_latitude, payload.origin_longitude],
        "destination": [payload.destination_latitude, payload.destination_longitude],
        "iat": int(time.time()), "exp": int(time.time()) + 600,
    }, settings.jwt_secret_key, algorithm="HS256")


def verify_route_token(token: str, user_uuid: str, from_id: str, to_id: str,
                       minutes: int, provider: str, queried_at: datetime,
                       mode: str, coordinate_system: str,
                       origin: list[float], destination: list[float]) -> bool:
    """判断候选路线是否来自该用户近期真实查询到的服务端结果。"""
    if not settings.jwt_secret_key:
        return False
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return False
    return (
        claims.get("typ") == "planning_route" and claims.get("sub") == user_uuid
        and claims.get("from") == from_id and claims.get("to") == to_id
        and claims.get("minutes") == minutes and claims.get("provider") == provider
        and claims.get("mode") == mode and claims.get("coordinateSystem") == coordinate_system
        and claims.get("origin") == origin and claims.get("destination") == destination
        and queried_at.tzinfo is not None
        and claims.get("queriedAt") == queried_at.isoformat()
    )


async def search_routes(payload: RouteSearchRequest, user_uuid: str) -> list[dict[str, Any]]:
    provider = provider_for(payload.country_code)
    expected_crs = "GCJ-02" if provider == "amap" else "WGS84"
    if payload.coordinate_system != expected_crs:
        raise AppException(f"该地区坐标需使用 {expected_crs}", status_code=422, code="MAP_COORDINATE_SYSTEM_MISMATCH")
    if provider == "apple_maps" and payload.mode == "transit":
        raise AppException("Apple Maps Server API 当前没有公交路线接口", status_code=422,
                           code="MAP_MODE_UNSUPPORTED")
    if payload.from_item_id == payload.to_item_id:
        raise AppException("路线起点和终点不能相同", status_code=422, code="MAP_ROUTE_INVALID")
    if not all(math.isfinite(value) for value in (
        payload.origin_latitude, payload.origin_longitude,
        payload.destination_latitude, payload.destination_longitude,
    )):
        raise AppException("坐标必须是有限数值", status_code=422, code="MAP_ROUTE_INVALID")
    if provider == "amap":
        path = {"walking": "/v3/direction/walking", "driving": "/v3/direction/driving",
                "transit": "/v5/direction/transit/integrated"}[payload.mode]
        params = {
            "origin": f"{payload.origin_longitude:.6f},{payload.origin_latitude:.6f}",
            "destination": f"{payload.destination_longitude:.6f},{payload.destination_latitude:.6f}",
        }
        if payload.mode == "transit":
            city_code = payload.city_code
            # 如果地点结果没有 citycode，通过高德行政区查询解析城市名称。
            if city_code is None:
                district = await _request(provider, "/v3/config/district", {
                    "keywords": payload.city, "subdistrict": 0, "extensions": "base",
                })
                matches = district.get("districts") or []
                codes = {str(entry.get("citycode") or "") for entry in matches}
                city_code = codes.pop() if len(codes) == 1 else ""
            if not city_code or not city_code.isdecimal():
                raise AppException("无法确定公交路线的城市编码", status_code=422,
                                   code="MAP_CITY_CODE_REQUIRED")
            params.update({"city1": city_code, "city2": city_code,
                           "show_fields": "cost,polyline"})
        data = await _request(provider, path, params)
        route = data.get("route") or {}
        options = route.get("transits") if payload.mode == "transit" else route.get("paths")
        options = options or []
        seconds_key = "duration"
    else:
        params = {
            "origin": f"{payload.origin_latitude},{payload.origin_longitude}",
            "destination": f"{payload.destination_latitude},{payload.destination_longitude}",
            "transportType": "Walking" if payload.mode == "walking" else "Automobile",
            "requestsAlternateRoutes": "true",
        }
        data = await _request(provider, "/v1/directions", params)
        options = data.get("routes") or []
        seconds_key = "durationSeconds"
    queried_at = datetime.now(timezone.utc).isoformat()
    results = []
    for index, option in enumerate(options[:3]):
        # 如果高德公交 2.0 将总耗时放在 cost 中，读取该服务实际返回的位置。
        duration = (option.get("cost") or {}).get("duration") if provider == "amap" and payload.mode == "transit" else option.get(seconds_key)
        if duration is None:
            continue
        try:
            duration_seconds = float(duration)
        except (TypeError, ValueError) as exc:
            raise AppException("地图服务返回了无效路线耗时", status_code=503,
                               code="MAP_PROVIDER_INVALID_RESPONSE") from exc
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise AppException("地图服务返回了无效路线耗时", status_code=503,
                               code="MAP_PROVIDER_INVALID_RESPONSE")
        minutes = math.ceil(duration_seconds / 60)
        route_choice_id = _route_token(user_uuid, payload, provider, minutes, queried_at, index)
        geometry = ""
        # 如果是高德路线，将真实路线几何短期绑定到签名引用，供同一用户预览。
        if provider == "amap":
            geometry = _amap_route_geometry(option, payload.mode)
            if geometry:
                redis = await get_redis_client()
                await redis.setex(
                    _route_preview_key(route_choice_id), 600,
                    json.dumps({"geometry": geometry,
                                "origin": [payload.origin_longitude, payload.origin_latitude],
                                "destination": [payload.destination_longitude, payload.destination_latitude]}),
                )
        results.append({
            "routeChoiceId": route_choice_id,
            "provider": provider, "mode": payload.mode, "coordinateSystem": expected_crs,
            "fromItemId": payload.from_item_id, "toItemId": payload.to_item_id,
            "routeDurationMinutes": minutes, "distanceMeters": option.get("distanceMeters", option.get("distance")),
            "queriedAt": queried_at, "expiresInSeconds": 600,
            "summary": option.get("name") or f"路线 {index + 1}",
            "previewAvailable": provider == "amap" and bool(geometry),
        })
    if not results:
        raise AppException("该地区和出行方式暂未查询到路线", status_code=404, code="MAP_ROUTE_NOT_FOUND")
    return results


def _route_preview_key(route_choice_id: str) -> str:
    return f"vago:planning-route-preview:{hashlib.sha256(route_choice_id.encode()).hexdigest()}"


def _amap_route_geometry(option: dict[str, Any], mode: str) -> str:
    """提取高德返回的实际路段折线；缺少路段时不绘制误导性的直线。"""
    if mode != "transit":
        steps = option.get("steps") or []
        parts = [step.get("polyline") for step in steps]
        return ";".join(parts) if parts and all(parts) else ""
    parts = []
    for segment in option.get("segments") or []:
        walking = (segment.get("walking") or {}).get("steps") or []
        buslines = (segment.get("bus") or {}).get("buslines") or []
        parts.extend((step.get("polyline") or {}).get("polyline") for step in walking)
        parts.extend((line.get("polyline") or {}).get("polyline") for line in buslines)
        if segment.get("railway") or not (walking or buslines):
            return ""
    return ";".join(parts) if parts and all(parts) else ""


async def route_preview_image(route_choice_id: str, user_uuid: str) -> tuple[bytes, str]:
    """仅允许路线归属用户读取由高德静态地图生成的预览。"""
    try:
        claims = jwt.decode(route_choice_id, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise AppException("路线引用已失效，请重新查询", status_code=422,
                           code="MAP_ROUTE_EXPIRED") from exc
    if claims.get("typ") != "planning_route" or claims.get("sub") != user_uuid or claims.get("provider") != "amap":
        raise AppException("无权预览该路线", status_code=403, code="MAP_ROUTE_FORBIDDEN")
    redis = await get_redis_client()
    cached = await redis.get(_route_preview_key(route_choice_id))
    if cached is None:
        raise AppException("路线预览已过期，请重新查询", status_code=410, code="MAP_ROUTE_EXPIRED")
    data = json.loads(cached)
    geometry = data["geometry"]
    if len(geometry) > 12000:
        raise AppException("路线过长，暂无法生成静态预览", status_code=422,
                           code="MAP_PREVIEW_TOO_LONG")
    origin = data["origin"]
    destination = data["destination"]
    params = {
        "key": settings.amap_web_key, "size": "760*440",
        "markers": (f"mid,0x7c3aed,A:{origin[0]:.6f},{origin[1]:.6f}"
                    f"|mid,0x0f766e,B:{destination[0]:.6f},{destination[1]:.6f}"),
        "paths": f"6,0x7c3aed,0.9,,:{geometry}",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get("https://restapi.amap.com/v3/staticmap", params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AppException("高德地图预览暂不可用", status_code=503,
                           code="MAP_PREVIEW_UNAVAILABLE") from exc
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/png") or not response.content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AppException("地图预览暂不可用", status_code=503, code="MAP_PREVIEW_UNAVAILABLE")
    return response.content, content_type
