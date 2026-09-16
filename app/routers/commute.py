"""
교통 라우터. 설계서 6.6 엔드포인트 명세 대응.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_guest_session_id, get_optional_user
from app.models.user import User
from app.schemas.commute import (
    CommuteCheckRequest,
    CommuteCheckResponse,
    CommuteFavoriteCreateRequest,
    CommuteFavoriteResponse,
    CommuteRouteCreateRequest,
    CommuteRouteResponse,
    FavoriteCommuteItem,
)
from app.schemas.common import ApiResponse
from app.services import commute_service

router = APIRouter(tags=["commute"])


@router.post("/commute/check", response_model=ApiResponse[CommuteCheckResponse])
async def check_commute(
    body: CommuteCheckRequest,
    current_user: User | None = Depends(get_optional_user),
    guest_session_id: str = Depends(get_guest_session_id),
    db: AsyncSession = Depends(get_db),
):
    """출발지·도착지 교통 확인. 인증: Optional."""
    user_id = current_user.id if current_user else None
    result = await commute_service.check_commute(
        user_id=user_id,
        use_default=body.use_default,
        origin_address=body.origin_address,
        destination_address=body.destination_address,
        db=db,
    )
    return ApiResponse(success=True, data=result)


@router.get("/users/me/commute-routes", response_model=ApiResponse[list[CommuteRouteResponse]])
async def list_commute_routes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """등록된 집/회사 경로 목록. 인증: Required."""
    routes = await commute_service.list_routes(current_user.id, db)
    return ApiResponse(
        success=True,
        data=[
            CommuteRouteResponse(
                id=r.id,
                label=r.label,
                address=r.address,
                latitude=r.latitude,
                longitude=r.longitude,
            )
            for r in routes
        ],
    )


@router.post("/users/me/commute-routes", response_model=ApiResponse[CommuteRouteResponse])
async def create_commute_route(
    body: CommuteRouteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """집/회사 주소 등록. 인증: Required."""
    route = await commute_service.create_route(
        user_id=current_user.id,
        label=body.label,
        address=body.address,
        lat=body.latitude,
        lng=body.longitude,
        db=db,
    )
    return ApiResponse(
        success=True,
        data=CommuteRouteResponse(
            id=route.id,
            label=route.label,
            address=route.address,
            latitude=route.latitude,
            longitude=route.longitude,
        ),
    )


@router.put("/users/me/commute-routes/{route_id}", response_model=ApiResponse[CommuteRouteResponse])
async def update_commute_route(
    route_id: int,
    body: CommuteRouteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """등록 경로 수정. 인증: Required."""
    route = await commute_service.update_route(
        route_id=route_id,
        user_id=current_user.id,
        label=body.label,
        address=body.address,
        lat=body.latitude,
        lng=body.longitude,
        db=db,
    )
    return ApiResponse(
        success=True,
        data=CommuteRouteResponse(
            id=route.id,
            label=route.label,
            address=route.address,
            latitude=route.latitude,
            longitude=route.longitude,
        ),
    )


@router.delete("/users/me/commute-routes/{route_id}", response_model=ApiResponse[None])
async def delete_commute_route(
    route_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """등록 경로 삭제. 인증: Required."""
    await commute_service.delete_route(route_id, current_user.id, db)
    return ApiResponse(success=True, data=None)


@router.get("/users/me/commute-favorites", response_model=ApiResponse[list[CommuteFavoriteResponse]])
async def list_commute_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """즐겨찾기 출발지-목적지 경로 목록. 인증: Required."""
    favorites = await commute_service.list_favorites(current_user.id, db)
    return ApiResponse(
        success=True,
        data=[
            CommuteFavoriteResponse(
                id=f.id,
                label=f.label,
                origin_address=f.origin_address,
                origin_lat=f.origin_lat,
                origin_lng=f.origin_lng,
                destination_address=f.destination_address,
                destination_lat=f.destination_lat,
                destination_lng=f.destination_lng,
            )
            for f in favorites
        ],
    )


@router.get(
    "/users/me/commute-favorites/commute", response_model=ApiResponse[list[FavoriteCommuteItem]]
)
async def get_commute_favorites_commute(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """즐겨찾기 경로들의 현재 소요시간. 인증: Required. 즐겨찾기가 없으면 빈 배열 반환."""
    items = await commute_service.get_favorites_commute(current_user.id, db)
    return ApiResponse(success=True, data=[FavoriteCommuteItem(**item) for item in items])


@router.post(
    "/users/me/commute-favorites", response_model=ApiResponse[CommuteFavoriteResponse], status_code=201
)
async def create_commute_favorite(
    body: CommuteFavoriteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """즐겨찾기 출발지-목적지 경로 추가 (최대 3개). 인증: Required."""
    favorite = await commute_service.add_favorite(
        current_user.id,
        body.label,
        body.origin_address, body.origin_lat, body.origin_lng,
        body.destination_address, body.destination_lat, body.destination_lng,
        db,
    )
    return ApiResponse(
        success=True,
        data=CommuteFavoriteResponse(
            id=favorite.id,
            label=favorite.label,
            origin_address=favorite.origin_address,
            origin_lat=favorite.origin_lat,
            origin_lng=favorite.origin_lng,
            destination_address=favorite.destination_address,
            destination_lat=favorite.destination_lat,
            destination_lng=favorite.destination_lng,
        ),
    )


@router.delete("/users/me/commute-favorites/{favorite_id}", response_model=ApiResponse[None])
async def delete_commute_favorite(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """즐겨찾기 경로 삭제. 인증: Required."""
    await commute_service.remove_favorite(favorite_id, current_user.id, db)
    return ApiResponse(success=True, data=None)


@router.put(
    "/users/me/commute-favorites/{favorite_id}",
    response_model=ApiResponse[CommuteFavoriteResponse],
)
async def update_commute_favorite(
    favorite_id: int,
    body: CommuteFavoriteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """즐겨찾기 출발지-목적지 경로 수정. 인증: Required."""
    favorite = await commute_service.update_favorite(
        favorite_id,
        current_user.id,
        body.label,
        body.origin_address,
        body.origin_lat,
        body.origin_lng,
        body.destination_address,
        body.destination_lat,
        body.destination_lng,
        db,
    )
    return ApiResponse(
        success=True,
        data=CommuteFavoriteResponse(
            id=favorite.id,
            label=favorite.label,
            origin_address=favorite.origin_address,
            origin_lat=favorite.origin_lat,
            origin_lng=favorite.origin_lng,
            destination_address=favorite.destination_address,
            destination_lat=favorite.destination_lat,
            destination_lng=favorite.destination_lng,
        ),
    )
