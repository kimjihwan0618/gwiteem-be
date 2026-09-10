"""
날씨 조회 클라이언트 (기상청 단기예보 - 초단기실황조회 API).
문서: https://www.data.go.kr/data/15084084/openapi.do
"""
import math
from datetime import datetime, timedelta

import httpx

from app.core.config import settings

KMA_NCST_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
KMA_VILLAGE_FORECAST_URL = (
    "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
)
_VILLAGE_FORECAST_BASE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)

# PTY(강수형태) 코드 -> 사용자에게 보여줄 condition 텍스트
_PTY_CONDITION = {
    "0": "맑음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}
_SKY_CONDITION = {
    "1": "맑음",
    "3": "구름많음",
    "4": "흐림",
}


def _latlng_to_grid(latitude: float, longitude: float) -> tuple[int, int]:
    """위경도 -> 기상청 격자좌표(nx, ny) 변환 (Lambert Conformal Conic 투영)."""
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0  # 격자 간격(km)
    SLAT1, SLAT2 = 30.0, 60.0  # 표준위도
    OLON, OLAT = 126.0, 38.0  # 기준점 경도/위도
    XO, YO = 43, 136  # 기준점 X, Y 좌표

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * DEGRAD, SLAT2 * DEGRAD
    olon, olat = OLON * DEGRAD, OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + latitude * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = longitude * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def _latest_base_datetime() -> tuple[str, str]:
    """
    초단기실황은 매시 40분에 생성되어 10분 뒤(50분)부터 조회 가능.
    현재 시각 기준 가장 최근에 확실히 존재하는 base_date/base_time을 계산.
    """
    now = datetime.now()
    if now.minute < 45:
        now -= timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")


def _latest_forecast_base_datetime() -> tuple[str, str]:
    """단기예보의 가장 최근 발표 시각을 계산한다."""
    cutoff = datetime.now() - timedelta(minutes=15)
    candidates = [
        cutoff.replace(hour=hour, minute=0, second=0, microsecond=0)
        for hour in _VILLAGE_FORECAST_BASE_HOURS
    ]
    candidates.extend(
        [
            (cutoff - timedelta(days=1)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            for hour in _VILLAGE_FORECAST_BASE_HOURS
        ]
    )
    base = max(candidate for candidate in candidates if candidate <= cutoff)
    return base.strftime("%Y%m%d"), base.strftime("%H00")


def _forecast_condition(values: dict[str, str]) -> str:
    precipitation = values.get("PTY", "0")
    if precipitation != "0":
        return _PTY_CONDITION.get(precipitation, "강수")
    return _SKY_CONDITION.get(values.get("SKY", "1"), "맑음")


async def get_current_weather(latitude: float, longitude: float) -> dict:
    """
    위경도 기준 현재 기온/강수 상태 조회.
    반환: {"temp_c": 21.3, "condition": "맑음"}
    """
    nx, ny = _latlng_to_grid(latitude, longitude)
    base_date, base_time = _latest_base_datetime()

    params = {
        "serviceKey": settings.WEATHER_API_KEY,
        "pageNo": 1,
        "numOfRows": 10,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(KMA_NCST_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        items = resp.json()["response"]["body"]["items"]["item"]

    values = {item["category"]: item["obsrValue"] for item in items}
    temp_c = float(values.get("T1H", 0))
    condition = _PTY_CONDITION.get(values.get("PTY", "0"), "맑음")

    return {"temp_c": temp_c, "condition": condition}


async def get_hourly_forecast(latitude: float, longitude: float) -> list[dict]:
    """현재 시각 이후 단기 시간대별 예보를 최대 24개 반환한다."""
    nx, ny = _latlng_to_grid(latitude, longitude)
    base_date, base_time = _latest_forecast_base_datetime()
    params = {
        "serviceKey": settings.WEATHER_API_KEY,
        "pageNo": 1,
        "numOfRows": 1000,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(KMA_VILLAGE_FORECAST_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        items = resp.json()["response"]["body"]["items"]["item"]

    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for item in items:
        key = (item["fcstDate"], item["fcstTime"])
        grouped.setdefault(key, {})[item["category"]] = item["fcstValue"]

    forecasts = []
    now = datetime.now()
    for (forecast_date, forecast_time), values in sorted(grouped.items()):
        forecast_datetime = datetime.strptime(
            f"{forecast_date}{forecast_time}", "%Y%m%d%H%M"
        )
        if "TMP" not in values or forecast_datetime <= now:
            continue
        forecasts.append(
            {
                "time": (
                    f"{forecast_date[:4]}-{forecast_date[4:6]}-"
                    f"{forecast_date[6:]}T{forecast_time[:2]}:"
                    f"{forecast_time[2:]}:00+09:00"
                ),
                "temp_c": float(values["TMP"]),
                "condition": _forecast_condition(values),
            }
        )
    return forecasts[:24]
