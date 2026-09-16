"""
교통 관련 스키마. 설계서 6.6 엔드포인트 명세 대응.
"""
from pydantic import BaseModel


class CommuteCheckRequest(BaseModel):
    origin_address: str | None = None
    destination_address: str | None = None
    use_default: bool = False


class LocationPoint(BaseModel):
    label: str | None = None
    lat: float
    lng: float


class RoutePoint(BaseModel):
    lat: float
    lng: float


class CommuteCheckResponse(BaseModel):
    origin: LocationPoint
    destination: LocationPoint
    estimated_minutes: int
    delay_minutes: int
    delay_reason: str | None = None
    recommended_departure_time: str | None = None
    route_polyline: list[RoutePoint] = []


class CommuteRouteCreateRequest(BaseModel):
    label: str  # HOME / WORK
    address: str
    latitude: float
    longitude: float


class CommuteRouteResponse(BaseModel):
    id: int
    label: str
    address: str
    latitude: float
    longitude: float
    is_default: bool


class CommuteFavoriteCreateRequest(BaseModel):
    label: str
    origin_address: str
    origin_lat: float
    origin_lng: float
    destination_address: str
    destination_lat: float
    destination_lng: float


class CommuteFavoriteResponse(BaseModel):
    id: int
    label: str
    origin_address: str
    origin_lat: float
    origin_lng: float
    destination_address: str
    destination_lat: float
    destination_lng: float


class CommuteEstimate(BaseModel):
    estimated_minutes: int
    delay_minutes: int
    delay_reason: str | None = None


class FavoriteCommuteItem(BaseModel):
    favorite: CommuteFavoriteResponse
    commute: CommuteEstimate
    route_polyline: list[RoutePoint] = []
