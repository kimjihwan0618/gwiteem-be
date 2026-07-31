"""
날씨 조회 비즈니스 로직.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException, InvalidRequestException, NotFoundException
from app.external import map_directions_client, weather_client
from app.repositories import weather_repo

MAX_FAVORITES = 3


async def get_weather(lat: float | None, lng: float | None) -> dict:
    """
    lat/lng 미지정 시 게스트 기본 지역(설정값)으로 대체.
    로그인 여부와 무관하게 좌표 기반으로 동작 - "원하는 지역"은 클라이언트가 lat/lng를 넘기는 방식으로 처리.
    """
    latitude = lat if lat is not None else settings.DEFAULT_WEATHER_LAT
    longitude = lng if lng is not None else settings.DEFAULT_WEATHER_LNG

    weather_result, forecast_result, address_result = await asyncio.gather(
        weather_client.get_current_weather(latitude, longitude),
        weather_client.get_hourly_forecast(latitude, longitude),
        map_directions_client.reverse_geocode(latitude, longitude),
        return_exceptions=True,
    )
    if isinstance(weather_result, BaseException):
        raise weather_result
    address = None if isinstance(address_result, BaseException) else address_result
    hourly = [] if isinstance(forecast_result, BaseException) else forecast_result

    return {
        "location": {"label": address, "lat": latitude, "lng": longitude},
        "weather": weather_result,
        "hourly": hourly,
    }


async def list_favorites(user_id: int, db: AsyncSession) -> list:
    return await weather_repo.list_favorites(user_id, db)


async def add_favorite(user_id: int, label: str, lat: float, lng: float, db: AsyncSession):
    existing = await weather_repo.list_favorites(user_id, db)
    if len(existing) >= MAX_FAVORITES:
        raise InvalidRequestException(
            message=f"날씨 즐겨찾기는 최대 {MAX_FAVORITES}개까지 등록할 수 있습니다.",
            code="WEATHER_FAVORITE_LIMIT_EXCEEDED",
        )

    favorite = await weather_repo.create_favorite(user_id, label, lat, lng, db)
    await db.commit()
    await db.refresh(favorite)
    return favorite


async def remove_favorite(favorite_id: int, user_id: int, db: AsyncSession) -> None:
    favorite = await weather_repo.get_favorite(favorite_id, db)
    if not favorite:
        raise NotFoundException("즐겨찾기를 찾을 수 없습니다.")
    if favorite.user_id != user_id:
        raise ForbiddenException()

    await weather_repo.delete_favorite(favorite_id, db)
    await db.commit()


async def get_favorites_weather(user_id: int, db: AsyncSession) -> list[dict]:
    """즐겨찾기 지역들의 현재 날씨를 각각 조회."""
    favorites = await weather_repo.list_favorites(user_id, db)

    items = []
    for favorite in favorites:
        weather = await weather_client.get_current_weather(favorite.latitude, favorite.longitude)
        items.append(
            {
                "favorite": {
                    "id": favorite.id,
                    "label": favorite.label,
                    "latitude": favorite.latitude,
                    "longitude": favorite.longitude,
                },
                "weather": weather,
            }
        )
    return items
