"""
교통 비즈니스 로직.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException, InvalidRequestException, NotFoundException
from app.external import map_directions_client
from app.models.commute import CommuteRoute
from app.repositories import commute_repo

MAX_COMMUTE_FAVORITES = 3


async def list_routes(user_id: int, db: AsyncSession) -> list[CommuteRoute]:
    return await commute_repo.list_routes(user_id, db)


async def create_route(
    user_id: int,
    label: str,
    address: str,
    lat: float,
    lng: float,
    db: AsyncSession,
) -> CommuteRoute:
    route = await commute_repo.create_route(user_id, label, address, lat, lng, db)
    await db.commit()
    await db.refresh(route)
    return route


async def update_route(
    route_id: int,
    user_id: int,
    label: str,
    address: str,
    lat: float,
    lng: float,
    db: AsyncSession,
) -> CommuteRoute:
    route = await commute_repo.get_route(route_id, db)
    if not route:
        raise NotFoundException("경로를 찾을 수 없습니다.")
    if route.user_id != user_id:
        raise ForbiddenException()
    route = await commute_repo.update_route(route, label, address, lat, lng, db)
    await db.commit()
    await db.refresh(route)
    return route


async def delete_route(route_id: int, user_id: int, db: AsyncSession) -> None:
    route = await commute_repo.get_route(route_id, db)
    if not route:
        raise NotFoundException("경로를 찾을 수 없습니다.")
    if route.user_id != user_id:
        raise ForbiddenException()
    await commute_repo.delete_route(route_id, db)
    await db.commit()


async def check_commute(
    user_id: int | None,
    use_default: bool,
    origin_address: str | None,
    destination_address: str | None,
    db: AsyncSession,
) -> dict:
    """
    1. use_default=True && 로그인 사용자면 CommuteRoute(HOME/WORK) 좌표 사용
    2. origin/destination 주소가 있으면 geocoding
    3. 둘 다 없으면(비로그인 기본값) 설정값(config)의 기본 경로 사용
    4. 길찾기 API 호출 -> estimated_minutes, delay_minutes 계산
    5. commute_repo.save_query() 로 로그 저장
    """
    if use_default and user_id:
        routes = await commute_repo.list_routes(user_id, db)
        home = next((r for r in routes if r.label == "HOME"), None)
        work = next((r for r in routes if r.label == "WORK"), None)
        if not home or not work:
            raise NotFoundException("등록된 집/회사 경로가 없습니다.")
        origin_label, origin_lat, origin_lng = home.address, home.latitude, home.longitude
        dest_label, dest_lat, dest_lng = work.address, work.latitude, work.longitude
    elif origin_address and destination_address:
        origin_label = origin_address
        dest_label = destination_address
        origin_lat, origin_lng = await map_directions_client.geocode(origin_address)
        dest_lat, dest_lng = await map_directions_client.geocode(destination_address)
    else:
        origin_label = settings.DEFAULT_COMMUTE_ORIGIN_LABEL
        origin_lat, origin_lng = settings.DEFAULT_COMMUTE_ORIGIN_LAT, settings.DEFAULT_COMMUTE_ORIGIN_LNG
        dest_label = settings.DEFAULT_COMMUTE_DESTINATION_LABEL
        dest_lat, dest_lng = settings.DEFAULT_COMMUTE_DESTINATION_LAT, settings.DEFAULT_COMMUTE_DESTINATION_LNG

    directions = await map_directions_client.get_directions(origin_lat, origin_lng, dest_lat, dest_lng)

    await commute_repo.save_query(
        user_id=user_id,
        origin_address=origin_label,
        destination_address=dest_label,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        estimated_minutes=directions["estimated_minutes"],
        delay_minutes=directions["delay_minutes"],
        db=db,
    )
    await db.commit()

    return {
        "origin": {"label": origin_label, "lat": origin_lat, "lng": origin_lng},
        "destination": {"label": dest_label, "lat": dest_lat, "lng": dest_lng},
        "estimated_minutes": directions["estimated_minutes"],
        "delay_minutes": directions["delay_minutes"],
        "delay_reason": directions["delay_reason"],
        "recommended_departure_time": None,
        "route_polyline": directions["route_polyline"],
    }


async def list_favorites(user_id: int, db: AsyncSession) -> list:
    return await commute_repo.list_favorites(user_id, db)


async def add_favorite(
    user_id: int,
    label: str,
    origin_address: str, origin_lat: float, origin_lng: float,
    destination_address: str, destination_lat: float, destination_lng: float,
    db: AsyncSession,
):
    existing = await commute_repo.list_favorites(user_id, db)
    if len(existing) >= MAX_COMMUTE_FAVORITES:
        raise InvalidRequestException(
            message=f"교통 즐겨찾기는 최대 {MAX_COMMUTE_FAVORITES}개까지 등록할 수 있습니다.",
            code="COMMUTE_FAVORITE_LIMIT_EXCEEDED",
        )

    favorite = await commute_repo.create_favorite(
        user_id, label,
        origin_address, origin_lat, origin_lng,
        destination_address, destination_lat, destination_lng,
        db,
    )
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def remove_favorite(favorite_id: int, user_id: int, db: AsyncSession) -> None:
    favorite = await commute_repo.get_favorite(favorite_id, db)
    if not favorite:
        raise NotFoundException("즐겨찾기를 찾을 수 없습니다.")
    if favorite.user_id != user_id:
        raise ForbiddenException()

    await commute_repo.delete_favorite(favorite_id, db)
    await db.commit()


async def update_favorite(
    favorite_id: int,
    user_id: int,
    label: str,
    origin_address: str,
    origin_lat: float,
    origin_lng: float,
    destination_address: str,
    destination_lat: float,
    destination_lng: float,
    db: AsyncSession,
):
    favorite = await commute_repo.get_favorite(favorite_id, db)
    if not favorite:
        raise NotFoundException("즐겨찾기를 찾을 수 없습니다.")
    if favorite.user_id != user_id:
        raise ForbiddenException()
    favorite = await commute_repo.update_favorite(
        favorite,
        label,
        origin_address,
        origin_lat,
        origin_lng,
        destination_address,
        destination_lat,
        destination_lng,
        db,
    )
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def get_favorites_commute(user_id: int, db: AsyncSession) -> list[dict]:
    """즐겨찾기 경로들의 현재 소요시간을 각각 조회. 로그 저장은 하지 않는다(main.py 새로고침 시 매번 쌓이지 않도록)."""
    favorites = await commute_repo.list_favorites(user_id, db)

    items = []
    for favorite in favorites:
        directions = await map_directions_client.get_directions(
            favorite.origin_lat, favorite.origin_lng,
            favorite.destination_lat, favorite.destination_lng,
        )
        items.append(
            {
                "favorite": {
                    "id": favorite.id,
                    "label": favorite.label,
                    "origin_address": favorite.origin_address,
                    "origin_lat": favorite.origin_lat,
                    "origin_lng": favorite.origin_lng,
                    "destination_address": favorite.destination_address,
                    "destination_lat": favorite.destination_lat,
                    "destination_lng": favorite.destination_lng,
                },
                "commute": {
                    "estimated_minutes": directions["estimated_minutes"],
                    "delay_minutes": directions["delay_minutes"],
                    "delay_reason": directions["delay_reason"],
                },
                "route_polyline": directions["route_polyline"],
            }
        )
    return items
