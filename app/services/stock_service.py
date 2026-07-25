"""
종목 관련 비즈니스 로직.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestException, NotFoundException
from app.external import stock_price_client
from app.repositories import interest_repo, news_repo, stock_repo

_MARKET_COUNTRY = {"domestic": "KR", "overseas": "US"}


async def search_stocks(query: str, db: AsyncSession) -> list[dict]:
    stocks = await stock_repo.search_by_name(query, db)
    return [{"code": s.code, "name": s.name, "market": s.market} for s in stocks]


async def get_stock_with_price(code: str, db: AsyncSession) -> dict:
    stock = await stock_repo.get_by_code(code, db)
    if not stock:
        raise NotFoundException(message="해당 종목을 찾을 수 없습니다.", code="STOCK_NOT_FOUND")

    price = await stock_price_client.get_current_price(code)
    history = await stock_price_client.get_price_history(code, days=7)
    issues = await news_repo.get_issues_by_stock_code(code, cursor_id=None, limit=5, db=db)

    return {
        "code": stock.code,
        "name": stock.name,
        "current_price": price["current_price"],
        "change_rate": price["change_rate"],
        "change_direction": price["change_direction"],
        "price_history_7d": history,
        "related_issues": [{"id": i.id, "title": i.title} for i in issues],
    }


async def get_top_stocks(market: str) -> list[dict]:
    """
    토스증권 거래대금 랭킹 API로 실시간 top3 조회. market: "domestic"(국내) | "overseas"(해외).
    종목명/시장구분은 로컬 stocks 테이블에 의존하지 않고 토스증권 API에서 바로 받아온다
    (비로그인 사용자가 별도 시딩 없이도 바로 조회 가능하도록).
    """
    market_country = _MARKET_COUNTRY.get(market)
    if not market_country:
        raise InvalidRequestException(
            message="market은 'domestic' 또는 'overseas'만 지원합니다.", code="INVALID_MARKET"
        )

    rankings = await stock_price_client.get_rankings(market_country, count=3)
    if not rankings:
        return []

    stock_info = await stock_price_client.get_stock_info([r["symbol"] for r in rankings])

    items = []
    for r in rankings:
        info = stock_info.get(r["symbol"])
        if not info:
            continue
        items.append(
            {
                "code": r["symbol"],
                "name": info["name"],
                "market": info["market"],
                "current_price": r["current_price"],
                "change_rate": r["change_rate"],
                "change_direction": r["change_direction"],
            }
        )
    return items


async def get_watchlist_market_impact(user_id: int, db: AsyncSession) -> list[dict]:
    interests = await interest_repo.list_user_interests(user_id, db)
    stock_codes = [i.value for i in interests if i.type == "STOCK"]

    items = []
    for code in stock_codes:
        stock = await stock_repo.get_by_code(code, db)
        if not stock:
            continue
        price = await stock_price_client.get_current_price(code)
        history = await stock_price_client.get_price_history(code, days=7)
        issues = await news_repo.get_issues_by_stock_code(code, cursor_id=None, limit=1, db=db)

        items.append(
            {
                "stock": {"code": stock.code, "name": stock.name, "market": stock.market},
                "related_issue_summary": issues[0].summary if issues else None,
                "current_price": price["current_price"],
                "change_rate": price["change_rate"],
                "change_direction": price["change_direction"],
                "sparkline_7d": history,
            }
        )
    return items
