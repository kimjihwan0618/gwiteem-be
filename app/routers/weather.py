"""
날씨 라우터.
"""
from fastapi import APIRouter, Query

from app.schemas.common import ApiResponse
from app.schemas.weather import WeatherResponse
from app.services import weather_service

router = APIRouter(tags=["weather"])


@router.get("/weather", response_model=ApiResponse[WeatherResponse])
async def get_current_weather(
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
):
    """현재 날씨 조회. 인증: Public. lat/lng 미지정 시 기본 지역(설정값) 사용."""
    result = await weather_service.get_weather(lat, lng)
    return ApiResponse(success=True, data=result)
