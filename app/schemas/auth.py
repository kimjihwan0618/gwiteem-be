"""
인증 관련 요청/응답 스키마. 설계서 6.1 엔드포인트 명세 대응.
"""
from pydantic import BaseModel


class LoginUrlResponse(BaseModel):
    login_url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str


class NicknameAvailabilityResponse(BaseModel):
    is_available: bool


class EmailVerificationSendRequest(BaseModel):
    email: str


class EmailVerificationConfirmRequest(BaseModel):
    email: str
    code: str


class PasswordResetSendRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    email: str
    code: str


class PasswordResetRequest(BaseModel):
    email: str
    new_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    id: int
    nickname: str
    profile_image_url: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    is_new_user: bool
    user: UserSummary


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
