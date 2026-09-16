"""
교통 경로 관련 DB 접근.
"""
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.commute import CommuteFavorite, CommuteQuery, CommuteRoute


async def list_routes(user_id: int, db: AsyncSession) -> list[CommuteRoute]:
    result = await db.execute(select(CommuteRoute).where(CommuteRoute.user_id == user_id))
    return list(result.scalars().all())


async def get_route(route_id: int, db: AsyncSession) -> CommuteRoute | None:
    result = await db.execute(select(CommuteRoute).where(CommuteRoute.id == route_id))
    return result.scalar_one_or_none()


async def create_route(user_id: int, label: str, address: str, lat: float, lng: float, db: AsyncSession) -> CommuteRoute:
    route = CommuteRoute(
        user_id=user_id,
        label=label,
        address=address,
        latitude=lat,
        longitude=lng,
    )
    db.add(route)
    await db.flush()
    return route


async def update_route(route: CommuteRoute, label: str, address: str, lat: float, lng: float, db: AsyncSession) -> CommuteRoute:
    route.label = label
    route.address = address
    route.latitude = lat
    route.longitude = lng
    db.add(route)
    return route


async def delete_route(route_id: int, db: AsyncSession) -> None:
    await db.execute(delete(CommuteRoute).where(CommuteRoute.id == route_id))


async def save_query(
    user_id: int | None,
    origin_address: str, destination_address: str,
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    estimated_minutes: int, delay_minutes: int,
    db: AsyncSession,
) -> CommuteQuery:
    query = CommuteQuery(
        user_id=user_id,
        origin_address=origin_address,
        destination_address=destination_address,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        estimated_minutes=estimated_minutes,
        delay_minutes=delay_minutes,
    )
    db.add(query)
    await db.flush()
    return query


async def list_favorites(user_id: int, db: AsyncSession) -> list[CommuteFavorite]:
    result = await db.execute(
        select(CommuteFavorite).where(CommuteFavorite.user_id == user_id).order_by(CommuteFavorite.id)
    )
    return list(result.scalars().all())


async def get_favorite(favorite_id: int, db: AsyncSession) -> CommuteFavorite | None:
    result = await db.execute(select(CommuteFavorite).where(CommuteFavorite.id == favorite_id))
    return result.scalar_one_or_none()


async def create_favorite(
    user_id: int,
    label: str,
    origin_address: str, origin_lat: float, origin_lng: float,
    destination_address: str, destination_lat: float, destination_lng: float,
    db: AsyncSession,
) -> CommuteFavorite:
    favorite = CommuteFavorite(
        user_id=user_id,
        label=label,
        origin_address=origin_address,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_address=destination_address,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
    )
    db.add(favorite)
    await db.flush()
    return favorite


async def update_favorite(
    favorite: CommuteFavorite,
    label: str,
    origin_address: str,
    origin_lat: float,
    origin_lng: float,
    destination_address: str,
    destination_lat: float,
    destination_lng: float,
    db: AsyncSession,
) -> CommuteFavorite:
    favorite.label = label
    favorite.origin_address = origin_address
    favorite.origin_lat = origin_lat
    favorite.origin_lng = origin_lng
    favorite.destination_address = destination_address
    favorite.destination_lat = destination_lat
    favorite.destination_lng = destination_lng
    db.add(favorite)
    return favorite


async def delete_favorite(favorite_id: int, db: AsyncSession) -> None:
    await db.execute(delete(CommuteFavorite).where(CommuteFavorite.id == favorite_id))
