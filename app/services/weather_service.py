"""
날씨 조회 비즈니스 로직.
"""
import asyncio

from app.core.config import settings
from app.external import map_directions_client, weather_client


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
