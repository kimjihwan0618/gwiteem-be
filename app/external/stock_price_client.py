"""
증권 시세 조회 클라이언트 (토스증권 Open API).
문서: https://developers.tossinvest.com/docs

- 토큰(OAuth2 client credentials)은 발급 후 Redis에 캐싱해 재사용.
- 시세 자체도 Redis에 1분 TTL로 캐싱해 API 호출 한도를 아낀다.
- /api/v1/prices 응답에는 전일대비 등락률/방향 필드가 없어(문서상 lastPrice만 보장됨),
  /api/v1/candles의 전일 종가와 비교해 change_rate/change_direction을 직접 계산한다.
"""
import httpx

from app.core.config import settings
from app.core.redis import redis_client

TOSS_BASE_URL = "https://openapi.tossinvest.com"
_TOKEN_CACHE_KEY = "toss:access_token"
_PRICE_CACHE_PREFIX = "toss:price:"
_HISTORY_CACHE_PREFIX = "toss:history:"
_RANKING_CACHE_PREFIX = "toss:ranking:"


async def _get_access_token() -> str:
    cached = await redis_client.get(_TOKEN_CACHE_KEY)
    if cached:
        return cached

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TOSS_BASE_URL}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.TOSS_SECURITIES_CLIENT_ID,
                "client_secret": settings.TOSS_SECURITIES_CLIENT_SECRET,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        body = resp.json()

    token = body["access_token"]
    expires_in = int(body.get("expires_in", 86400))
    await redis_client.set(_TOKEN_CACHE_KEY, token, ex=max(expires_in - 60, 60))
    return token


async def _auth_headers() -> dict:
    token = await _get_access_token()
    return {"Authorization": f"Bearer {token}"}


async def _fetch_daily_candles(stock_code: str, count: int) -> list[dict]:
    """최근 순(최신 -> 과거)으로 정렬된 일봉 캔들 리스트를 반환."""
    headers = await _auth_headers()
    params = {"symbol": stock_code, "interval": "1d", "count": count}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TOSS_BASE_URL}/api/v1/candles",
            headers=headers,
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["candles"]


async def get_current_price(stock_code: str) -> dict:
    """
    반환 예시: {"current_price": 71800, "change_rate": 1.27, "change_direction": "UP"}
    """
    cache_key = f"{_PRICE_CACHE_PREFIX}{stock_code}"
    cached = await redis_client.hgetall(cache_key)
    if cached:
        return {
            "current_price": float(cached["current_price"]),
            "change_rate": float(cached["change_rate"]),
            "change_direction": cached["change_direction"],
        }

    headers = await _auth_headers()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TOSS_BASE_URL}/api/v1/prices",
            headers=headers,
            params={"symbols": stock_code},
            timeout=10.0,
        )
        resp.raise_for_status()
        current_price = float(resp.json()["result"][0]["lastPrice"])

    candles = await _fetch_daily_candles(stock_code, count=2)
    prev_close = float(candles[1]["closePrice"]) if len(candles) > 1 else current_price

    change_rate = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
    if current_price > prev_close:
        change_direction = "UP"
    elif current_price < prev_close:
        change_direction = "DOWN"
    else:
        change_direction = "FLAT"

    result = {
        "current_price": current_price,
        "change_rate": change_rate,
        "change_direction": change_direction,
    }

    await redis_client.hset(cache_key, mapping=result)
    await redis_client.expire(cache_key, 60)
    return result


async def get_price_history(stock_code: str, days: int = 7) -> list[float]:
    """일별 종가 리스트 반환 (오래된 날짜 -> 최근 날짜 순)."""
    cache_key = f"{_HISTORY_CACHE_PREFIX}{stock_code}:{days}"
    cached = await redis_client.get(cache_key)
    if cached:
        return [float(v) for v in cached.split(",")]

    candles = await _fetch_daily_candles(stock_code, count=days)
    closes = [float(c["closePrice"]) for c in candles[:days]]
    closes.reverse()  # API가 최신순으로 내려주므로 오래된 순으로 뒤집음

    await redis_client.set(cache_key, ",".join(str(c) for c in closes), ex=60)
    return closes


async def get_rankings(market_country: str, duration: str = "realtime", count: int = 5) -> list[dict]:
    """
    거래대금 상위 종목 랭킹 조회. market_country: "KR" | "US".
    duration: "realtime" | "1d" | "1w" | "1mo" (토스증권 API 지원값)
    반환 예시: [{"symbol": "005930", "current_price": 71800, "change_rate": 1.25, "change_direction": "UP"}]
    """
    cache_key = f"{_RANKING_CACHE_PREFIX}{market_country}:{duration}:{count}"
    cached = await redis_client.get(cache_key)
    if cached:
        items = []
        for entry in cached.split("|"):
            symbol, price, rate, direction = entry.split(",")
            items.append(
                {
                    "symbol": symbol,
                    "current_price": float(price),
                    "change_rate": float(rate),
                    "change_direction": direction,
                }
            )
        return items

    headers = await _auth_headers()
    params = {
        "type": "MARKET_TRADING_AMOUNT",
        "marketCountry": market_country,
        "duration": duration,
        "count": count,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TOSS_BASE_URL}/api/v1/rankings",
            headers=headers,
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        rankings = resp.json()["result"]["rankings"]

    items = []
    for entry in rankings:
        change_rate = round(float(entry["price"]["changeRate"]) * 100, 2)
        if change_rate > 0:
            change_direction = "UP"
        elif change_rate < 0:
            change_direction = "DOWN"
        else:
            change_direction = "FLAT"
        items.append(
            {
                "symbol": entry["symbol"],
                "current_price": float(entry["price"]["lastPrice"]),
                "change_rate": change_rate,
                "change_direction": change_direction,
            }
        )

    await redis_client.set(
        cache_key,
        "|".join(f"{i['symbol']},{i['current_price']},{i['change_rate']},{i['change_direction']}" for i in items),
        ex=60,
    )
    return items


async def get_stock_info(symbols: list[str]) -> dict[str, dict]:
    """종목 심볼 -> {"name": 한글명, "market": 시장구분(KOSPI/KOSDAQ/NASDAQ 등)} 매핑."""
    if not symbols:
        return {}

    headers = await _auth_headers()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TOSS_BASE_URL}/api/v1/stocks",
            headers=headers,
            params={"symbols": ",".join(symbols)},
            timeout=10.0,
        )
        resp.raise_for_status()
        stocks = resp.json()["result"]

    return {s["symbol"]: {"name": s["name"], "market": s["market"]} for s in stocks}
