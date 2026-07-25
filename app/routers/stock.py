"""
종목 라우터. 설계서 6.5 엔드포인트 명세 대응.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.repositories import news_repo, stock_repo
from app.schemas.common import ApiResponse
from app.schemas.news import IssueListResponse, IssueSummary
from app.schemas.stock import StockDetailResponse, StockSearchResult, WatchlistImpactItem
from app.services import stock_service

router = APIRouter(tags=["stock"])


@router.get("/stocks/top", response_model=ApiResponse[list[StockDetailResponse]])
async def get_top_stocks(
    market: str = Query(default="domestic"),
    duration: str = Query(default="realtime"),
):
    """
    비로그인 메인 화면용 인기 종목 top5. 인증: Public.
    market: domestic(국내) | overseas(해외). duration: realtime | 1d | 1w | 1mo.
    """
    items = await stock_service.get_top_stocks(market, duration)
    return ApiResponse(success=True, data=[StockDetailResponse(**item) for item in items])


@router.get("/stocks/search", response_model=ApiResponse[list[StockSearchResult]])
async def search_stocks(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    """종목명/코드 검색(자동완성). 인증: Public."""
    results = await stock_service.search_stocks(q, db)
    return ApiResponse(success=True, data=[StockSearchResult(**r) for r in results])


@router.get("/stocks/{code}", response_model=ApiResponse[StockDetailResponse])
async def get_stock_detail(code: str, db: AsyncSession = Depends(get_db)):
    """종목 현재가/등락률 + 관련 뉴스 이슈. 인증: Public."""
    result = await stock_service.get_stock_with_price(code, db)
    return ApiResponse(success=True, data=StockDetailResponse(**result))


@router.get("/stocks/{code}/news", response_model=ApiResponse[IssueListResponse])
async def get_stock_news(
    code: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """특정 종목 관련 뉴스만 필터링. 인증: Public."""
    stock = await stock_repo.get_by_code(code, db)
    if not stock:
        return ApiResponse(
            success=True,
            data=IssueListResponse(total_raw_articles=0, total_issues=0, issues=[]),
        )

    cursor_id = int(cursor) if cursor else None
    issues = await news_repo.get_issues_by_stock_code(code, cursor_id, limit, db)

    next_cursor = str(issues[-1].id) if len(issues) == limit else None
    return ApiResponse(
        success=True,
        data=IssueListResponse(
            total_raw_articles=sum(i.article_count for i in issues),
            total_issues=len(issues),
            issues=[
                IssueSummary(id=i.id, category=i.category, article_count=i.article_count, title=i.title)
                for i in issues
            ],
            next_cursor=next_cursor,
        ),
    )


@router.get("/users/me/watchlist/market-impact", response_model=ApiResponse[list[WatchlistImpactItem]])
async def get_watchlist_market_impact(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로그인 사용자의 관심 종목 "오늘의 영향" 카드. 인증: Required."""
    items = await stock_service.get_watchlist_market_impact(current_user.id, db)
    return ApiResponse(success=True, data=[WatchlistImpactItem(**item) for item in items])
