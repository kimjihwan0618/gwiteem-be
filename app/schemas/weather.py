"""
날씨 관련 스키마.
"""
from pydantic import BaseModel, Field

from app.schemas.commute import LocationPoint


class WeatherInfo(BaseModel):
    temp_c: float
    condition: str


class HourlyWeather(BaseModel):
    time: str
    temp_c: float
    condition: str


class WeatherResponse(BaseModel):
    location: LocationPoint
    weather: WeatherInfo
    hourly: list[HourlyWeather] = Field(default_factory=list)
