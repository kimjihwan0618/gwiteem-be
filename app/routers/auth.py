"""
인증 라우터. 설계서 6.1 엔드포인트 명세 대응.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.exceptions import InvalidRequestException, UnauthorizedException
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.repositories import user_repo
from app.schemas.auth import (
    AccessTokenResponse,
    EmailVerificationConfirmRequest,
    EmailVerificationSendRequest,
    LoginRequest,
    LoginUrlResponse,
    NicknameAvailabilityResponse,
    LogoutRequest,
    OAuthCallbackRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetSendRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserSummary,
)
from app.schemas.common import ApiResponse
from app.services import auth_service
from app.external.oauth_client import SUPPORTED_PROVIDERS, build_authorize_url

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/nickname/availability",
    response_model=ApiResponse[NicknameAvailabilityResponse],
)
async def check_nickname_availability(
    nickname: str,
    db: AsyncSession = Depends(get_db),
):
    """회원가입 닉네임 사용 가능 여부 확인. 인증: Public."""
    is_available = await auth_service.is_nickname_available(nickname, db)
    return ApiResponse(
        success=True,
        data=NicknameAvailabilityResponse(is_available=is_available),
    )


@router.get("/{provider}/login-url", response_model=ApiResponse[LoginUrlResponse])
async def get_login_url(provider: str):
    """소셜 로그인 진입 URL 발급. 인증: Public."""
    if provider not in SUPPORTED_PROVIDERS:
        raise InvalidRequestException(f"지원하지 않는 provider입니다: {provider}")

    url = build_authorize_url(provider)
    return ApiResponse(success=True, data=LoginUrlResponse(login_url=url))


@router.post("/{provider}/callback", response_model=ApiResponse[TokenResponse])
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """소셜 로그인 콜백 처리 → 회원가입/로그인 + JWT 발급. 인증: Public."""
    if provider not in SUPPORTED_PROVIDERS:
        raise InvalidRequestException(f"지원하지 않는 provider입니다: {provider}")

    user, is_new_user = await auth_service.handle_oauth_callback(
        provider, body.code, body.state, db
    )
    tokens = await auth_service.issue_tokens(user)

    return ApiResponse(
        success=True,
        data=TokenResponse(
            **tokens,
            is_new_user=is_new_user,
            user=UserSummary(
                id=user.id,
                nickname=user.nickname,
                profile_image_url=user.profile_image_url,
            ),
        ),
    )


@router.post("/email/verification-code", response_model=ApiResponse[None])
async def send_email_verification_code(body: EmailVerificationSendRequest, db: AsyncSession = Depends(get_db)):
    """회원가입용 이메일 인증번호 발송. 인증: Public."""
    await auth_service.send_email_verification_code(body.email, db)
    return ApiResponse(success=True, data=None)


@router.post("/email/verification-code/confirm", response_model=ApiResponse[None])
async def confirm_email_verification_code(body: EmailVerificationConfirmRequest):
    """이메일 인증번호 검증. 인증: Public."""
    await auth_service.verify_email_code(body.email, body.code)
    return ApiResponse(success=True, data=None)


@router.post("/password/reset-code", response_model=ApiResponse[None])
async def send_password_reset_code(body: PasswordResetSendRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 인증번호 발송. 인증: Public."""
    await auth_service.send_password_reset_code(body.email, db)
    return ApiResponse(success=True, data=None)


@router.post("/password/reset-code/confirm", response_model=ApiResponse[None])
async def confirm_password_reset_code(body: PasswordResetConfirmRequest):
    """비밀번호 재설정 인증번호 검증. 인증: Public."""
    await auth_service.verify_password_reset_code(body.email, body.code)
    return ApiResponse(success=True, data=None)


@router.post("/password/reset", response_model=ApiResponse[None])
async def reset_password(body: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """인증번호 검증 통과 후 새 비밀번호로 재설정. 인증: Public."""
    await auth_service.reset_password(body.email, body.new_password, db)
    return ApiResponse(success=True, data=None)


@router.post("/register", response_model=ApiResponse[TokenResponse])
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """이메일/비밀번호 회원가입 → 로그인 + JWT 발급. 인증: Public."""
    user, is_new_user = await auth_service.register_local_user(body.email, body.password, body.nickname, db)
    tokens = await auth_service.issue_tokens(user)

    return ApiResponse(
        success=True,
        data=TokenResponse(
            **tokens,
            is_new_user=is_new_user,
            user=UserSummary(
                id=user.id,
                nickname=user.nickname,
                profile_image_url=user.profile_image_url,
            ),
        ),
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """이메일/비밀번호 로그인. 인증: Public."""
    user = await auth_service.login_local_user(body.email, body.password, db)
    tokens = await auth_service.issue_tokens(user)

    return ApiResponse(
        success=True,
        data=TokenResponse(
            **tokens,
            is_new_user=False,
            user=UserSummary(
                id=user.id,
                nickname=user.nickname,
                profile_image_url=user.profile_image_url,
            ),
        ),
    )


@router.post("/refresh", response_model=ApiResponse[AccessTokenResponse])
async def refresh_access_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """refresh_token으로 access_token 재발급. 인증: Public."""
    payload = decode_token(body.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedException(message="유효하지 않은 refresh token입니다.", code="INVALID_REFRESH_TOKEN")

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not jti or not await auth_service.verify_refresh_session(int(user_id), jti):
        raise UnauthorizedException(message="로그아웃되었거나 만료된 세션입니다.", code="INVALID_REFRESH_TOKEN")

    user = await user_repo.get_by_id(int(user_id), db)
    if user is None:
        raise UnauthorizedException(message="존재하지 않는 사용자입니다.", code="INVALID_REFRESH_TOKEN")

    from app.core.config import settings
    new_access_token = create_access_token(user.id)

    return ApiResponse(
        success=True,
        data=AccessTokenResponse(
            access_token=new_access_token,
            expires_in=settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
        ),
    )


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    body: LogoutRequest,
    current_user: User = Depends(get_current_user),
):
    """로그아웃. 인증: Required. 요청한 기기(refresh_token)의 세션만 Redis에서 무효화하고 다른 기기 로그인은 유지된다."""
    await auth_service.logout(current_user.id, body.refresh_token)
    return ApiResponse(success=True, data=None)


@router.delete("/withdraw", response_model=ApiResponse[None])
async def withdraw(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회원 탈퇴. 인증: Required."""
    await auth_service.withdraw_user(current_user.id, db)
    return ApiResponse(success=True, data=None)
